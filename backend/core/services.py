import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP, localcontext

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import AuditEvent, Business, Expense, Product, Receipt, ReceiptLine, StockMovement


def audit(business, actor, action, target, **details):
    AuditEvent.objects.create(business=business, actor=actor, action=action,
                              target_id=target.pk, details=details)


def expense_values(expense):
    return {"amount": str(expense.amount), "incurred_on": str(expense.incurred_on),
            "category_id": expense.category_id, "method": expense.method,
            "description": expense.description, "voided": expense.voided}


@transaction.atomic
def record_expense(business, actor, data):
    expense = Expense.objects.create(business=business, actor=actor, **data)
    audit(business, actor, "expense.recorded", expense, after=expense_values(expense))
    return expense


def add_stock(product, quantity, unit_cost, kind, actor, line=None):
    balance = product.stock + quantity
    if balance >= Decimal("100000000000"):
        raise ValidationError({"quantity": "This would exceed the supported stock balance."})
    with localcontext() as context:
        context.prec = 40
        product.cost = ((product.stock * product.cost + quantity * unit_cost) / balance).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
    product.stock = balance
    product.save(update_fields=["stock", "cost", "updated_at"])
    return StockMovement.objects.create(
        business=product.business, product=product, kind=kind, quantity=quantity,
        balance=balance, unit_cost=unit_cost, actor=actor, receipt_line=line,
    )


@transaction.atomic
def open_stock(business, actor, product_id, quantity, unit_cost):
    product = Product.objects.select_for_update().filter(business=business, pk=product_id).first()
    if not product or not product.active or not product.track_stock:
        raise ValidationError({"product": "Choose an active stock-tracked product."})
    if StockMovement.objects.filter(product=product).exists():
        raise ValidationError({"product": "Opening stock is only allowed before the first movement."})
    movement = add_stock(product, quantity, unit_cost, StockMovement.Kind.OPENING, actor)
    audit(business, actor, "stock.opened", product, quantity=str(quantity), unit_cost=str(unit_cost))
    return movement


@transaction.atomic
def increase_stock(business, actor, product_id, quantity, reason):
    product = Product.objects.select_for_update().filter(
        business=business, pk=product_id, active=True, track_stock=True
    ).first()
    if not product or quantity <= 0 or not reason.strip():
        raise ValidationError("An incoming adjustment requires a tracked product, a positive quantity, and a reason.")
    if product.stock <= 0 and not StockMovement.objects.filter(product=product).exists():
        raise ValidationError("Use opening stock or a purchase receipt to establish inventory cost.")
    movement = add_stock(product, quantity, product.cost, StockMovement.Kind.ADJUSTMENT, actor)
    audit(business, actor, "stock.adjusted", movement, product_id=product.pk, quantity=str(quantity), reason=reason)
    return movement


@transaction.atomic
def receive_stock(business, actor, request_id, supplier, received_on, reference, lines):
    # Serialize receipts per business to make retry checks and receipt creation atomic.
    Business.objects.select_for_update().get(pk=business.pk)
    lines = sorted(lines, key=lambda line: line["product"])
    payload = [supplier.pk, received_on.isoformat(), reference, lines]
    fingerprint = hashlib.sha256(json.dumps(payload, default=str, sort_keys=True).encode()).hexdigest()
    prior = Receipt.objects.filter(business=business, request_id=request_id).first()
    if prior:
        if prior.fingerprint != fingerprint:
            raise ValidationError({"request_id": "This receipt key was already used with different details."})
        return prior, False
    if not supplier.active:
        raise ValidationError({"supplier": "Choose an active supplier."})
    ids = [line["product"] for line in lines]
    if len(set(ids)) != len(ids):
        raise ValidationError({"lines": "Include each product once."})
    products = {p.pk: p for p in Product.objects.select_for_update().filter(
        business=business, pk__in=ids, active=True, track_stock=True
    ).order_by("pk")}
    if len(products) != len(ids):
        raise ValidationError({"lines": "Choose active stock-tracked products from this business."})
    receipt = Receipt.objects.create(business=business, actor=actor, request_id=request_id,
                                     supplier=supplier, received_on=received_on,
                                     reference=reference, fingerprint=fingerprint)
    for item in lines:
        product = products[item["product"]]
        line = ReceiptLine.objects.create(business=business, receipt=receipt, product=product,
                                          quantity=item["quantity"], unit_cost=item["unit_cost"])
        add_stock(product, line.quantity, line.unit_cost, StockMovement.Kind.PURCHASE, actor, line)
    audit(business, actor, "purchase.received", receipt, line_count=len(lines))
    return receipt, True
