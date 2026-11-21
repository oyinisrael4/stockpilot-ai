import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP, localcontext
from functools import wraps

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from .models import Business, Customer, Product, ReturnLine, Sale, SaleLine, SalePayment, SaleReturn, StockMovement
from .services import add_stock, audit

ZERO = Decimal("0.00")


def money(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def exact_finance(function):
    @wraps(function)
    def run(*args, **kwargs):
        with localcontext() as context:
            context.prec = 60
            return function(*args, **kwargs)
    return run


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()


def discount_amount(base, discount):
    value = discount["value"]
    amount = money(base * value / 100) if discount["kind"] == "percent" else value
    if amount > base:
        raise ValidationError("A fixed discount cannot exceed the amount it applies to.")
    return amount


@exact_finance
def calculate(business, data, *, lock=False, check_stock=True):
    items = sorted(data["lines"], key=lambda line: line["product"])
    ids = [item["product"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValidationError({"lines": "Include each product once."})
    queryset = Product.objects.filter(business=business, pk__in=ids, active=True).order_by("pk")
    products = {product.pk: product for product in (queryset.select_for_update() if lock else queryset)}
    if len(products) != len(ids):
        raise ValidationError({"lines": "Choose active products in this workspace."})
    lines = []
    for item in items:
        product = products[item["product"]]
        quantity = item["quantity"]
        if product.unit not in ("kg", "litre") and quantity != quantity.to_integral_value():
            raise ValidationError({"lines": f"{product.name} must be sold in whole {product.unit} quantities."})
        if check_stock and product.track_stock and quantity > product.stock:
            raise ValidationError({"lines": f"Insufficient stock for {product.name}. Available: {product.stock}."})
        subtotal = money(quantity * product.price)
        line_discount = discount_amount(subtotal, item["discount"])
        lines.append(dict(product=product, name=product.name, sku=product.sku, unit=product.unit,
                          tracked=product.track_stock, quantity=quantity, price=product.price,
                          unit_cost=product.cost, subtotal=subtotal, discount=line_discount,
                          cogs=money(quantity * product.cost)))
    base = sum((line["subtotal"] - line["discount"] for line in lines), ZERO)
    invoice_discount = discount_amount(base, data["discount"])
    cumulative = allocated = ZERO
    for line in lines:
        cumulative += line["subtotal"] - line["discount"]
        share_through_line = money(invoice_discount * cumulative / base) if base else ZERO
        line["discount"] += share_through_line - allocated
        allocated = share_through_line
        taxable_base = line["subtotal"] - line["discount"]
        line["tax"] = money(taxable_base * business.tax_rate / 100) if line["product"].taxable else ZERO
        line["total"] = taxable_base + line["tax"]
    totals = {field: sum((line[field] for line in lines), ZERO)
              for field in ("subtotal", "discount", "tax", "total", "cogs")}
    return lines, totals


def get_customer(business, customer_id):
    if customer_id is None:
        return None
    customer = Customer.objects.filter(business=business, pk=customer_id, active=True).first()
    if not customer:
        raise ValidationError({"customer": "Choose an active customer in this workspace."})
    return customer


@transaction.atomic
@exact_finance
def save_sale(business, actor, data, *, draft=False):
    business = Business.objects.select_for_update().get(pk=business.pk)
    key = data["request_id"]
    digest = fingerprint(data)
    sale = Sale.objects.filter(business=business, request_id=key).first()
    if sale and sale.status != Sale.Status.DRAFT:
        if not draft and sale.fingerprint == digest and sale.posted_at:
            return sale, False
        raise ValidationError({"request_id": "This sale reference is already closed."})
    customer = get_customer(business, data["customer"])
    lines, totals = calculate(business, data, lock=not draft, check_stock=not draft)
    sale = sale or Sale(business=business, request_id=key, actor=actor)
    sale.customer = customer
    sale.customer_name = customer.name if customer else ""
    sale.notes = data["notes"]
    if draft:
        sale.draft = json.loads(json.dumps(data, default=str))
        sale.save()
        audit(business, actor, "sale.draft_saved", sale)
        return sale, True
    payments = data["payments"]
    paid = sum((item["amount"] for item in payments), ZERO)
    if paid > totals["total"]:
        raise ValidationError({"payments": "Payments cannot exceed the sale total."})
    if paid < totals["total"] and not customer:
        raise ValidationError({"customer": "Select a registered customer for an outstanding balance."})
    if data["expected_total"] != totals["total"]:
        raise ValidationError({"expected_total": "The total changed. Review a fresh quote before posting."})
    for field, value in totals.items():
        setattr(sale, field, value)
    sale.paid = paid
    sale.fingerprint = digest
    sale.status = Sale.Status.COMPLETED
    sale.posted_at = timezone.now()
    sale.draft = {}
    sale.actor = actor
    sale.save()
    for item in lines:
        line = SaleLine.objects.create(sale=sale, business=business, **item)
        product = line.product
        if line.tracked:
            product.stock -= line.quantity
            product.save(update_fields=["stock", "updated_at"])
            StockMovement.objects.create(business=business, product=product, actor=actor, kind=StockMovement.Kind.SALE,
                                         quantity=-line.quantity, balance=product.stock, unit_cost=line.unit_cost, sale_line=line)
    SalePayment.objects.bulk_create([SalePayment(business=business, actor=actor, sale=sale, **item) for item in payments])
    audit(business, actor, "sale.posted", sale, total=str(sale.total), paid=str(paid))
    return sale, True


def find_sale(business, sale_id):
    sale = Sale.objects.filter(business=business, pk=sale_id).first()
    if not sale:
        raise NotFound("Sale not found in this workspace.")
    return sale


@transaction.atomic
@exact_finance
def record_payment(business, actor, sale_id, data):
    Business.objects.select_for_update().get(pk=business.pk)
    sale = find_sale(business, sale_id)
    prior = SalePayment.objects.filter(business=business, request_id=data["request_id"]).first()
    if prior:
        if prior.sale_id == sale_id and prior.amount == data["amount"] and prior.method == data["method"]:
            return sale
        raise ValidationError({"request_id": "This payment reference has already been used."})
    if sale.status != Sale.Status.COMPLETED or data["amount"] > sale.balance:
        raise ValidationError({"amount": "Payment must fit the outstanding balance on a completed sale."})
    SalePayment.objects.create(business=business, actor=actor, sale=sale, **data)
    sale.paid += data["amount"]
    sale.save(update_fields=["paid"])
    audit(business, actor, "sale.payment_recorded", sale, amount=str(data["amount"]), method=data["method"])
    return sale


def portion(amount, line, quantity):
    already = line.returned_quantity
    return money(amount * (already + quantity) / line.quantity) - money(amount * already / line.quantity)


@transaction.atomic
@exact_finance
def reverse_sale(business, actor, sale_id, data, *, void=False, preview=False):
    Business.objects.select_for_update().get(pk=business.pk)
    sale = find_sale(business, sale_id)
    digest = fingerprint([sale_id, void, data])
    prior = SaleReturn.objects.filter(business=business, request_id=data["request_id"]).first()
    if prior:
        if prior.fingerprint != digest:
            raise ValidationError({"request_id": "This reversal reference has already been used."})
        return prior, False
    if sale.status != Sale.Status.COMPLETED and not (void and sale.status == Sale.Status.DRAFT):
        raise ValidationError("Only completed sales can be returned. Drafts can be voided.")
    originals = {line.pk: line for line in sale.lines.all()}
    requested = ([{"sale_line": line.pk, "quantity": line.quantity - line.returned_quantity, "restocked": line.tracked}
                  for line in originals.values() if line.quantity > line.returned_quantity] if void else data["lines"])
    product_ids = [line.product_id for line in originals.values()]
    products = {product.pk: product for product in Product.objects.select_for_update().filter(
        business=business, pk__in=product_ids).order_by("pk")}
    seen = set()
    lines = []
    for item in requested:
        original = originals.get(item["sale_line"])
        quantity = item["quantity"]
        if not original or original.pk in seen or quantity + original.returned_quantity > original.quantity:
            raise ValidationError({"lines": "Return each original line at most once and within its remaining quantity."})
        if original.unit not in ("kg", "litre") and quantity != quantity.to_integral_value():
            raise ValidationError({"lines": "Return whole quantities for discrete units."})
        seen.add(original.pk)
        restocked = item["restocked"] and original.tracked
        tax = portion(original.tax, original, quantity)
        net = portion(original.total - original.tax, original, quantity)
        cogs = portion(original.cogs, original, quantity) if restocked else ZERO
        lines.append(dict(sale_line=original, quantity=quantity, restocked=restocked, total=net + tax,
                          tax=tax, cogs_reversed=cogs))
    totals = {field: sum((line[field] for line in lines), ZERO) for field in ("total", "tax", "cogs_reversed")}
    refund = max(ZERO, totals["total"] - sale.balance)
    if preview:
        return {"total": f"{totals['total']:.2f}", "refund": f"{refund:.2f}",
                "receivable_reduction": f"{totals['total'] - refund:.2f}"}
    if data["expected_refund"] != refund:
        raise ValidationError({"expected_refund": f"The refund required is {refund:.2f}. Review before recording."})
    if refund and not data["refund_method"]:
        raise ValidationError({"refund_method": "Select how the refund was paid."})
    reversal = SaleReturn.objects.create(
        business=business, actor=actor, sale=sale, request_id=data["request_id"], reason=data["reason"],
        fingerprint=digest, void=void, refund=refund, refund_method=data["refund_method"] if refund else "", **totals,
    )
    for item in lines:
        line = ReturnLine.objects.create(business=business, sale_return=reversal, **item)
        original = line.sale_line
        original.returned_quantity += line.quantity
        original.save(update_fields=["returned_quantity"])
        if line.restocked:
            movement = add_stock(products[original.product_id], line.quantity, original.unit_cost,
                                 StockMovement.Kind.VOID if void else StockMovement.Kind.RETURN, actor)
            movement.return_line = line
            movement.save(update_fields=["return_line"])
    sale.returned += reversal.total
    sale.paid -= refund
    if void:
        sale.status = Sale.Status.VOIDED
        sale.draft = {}
    sale.save(update_fields=["returned", "paid", "status", "draft"])
    audit(business, actor, "sale.voided" if void else "sale.returned", sale, reversal=reversal.pk, reason=data["reason"])
    return reversal, True
