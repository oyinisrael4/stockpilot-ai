import re
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers as s
from rest_framework.exceptions import PermissionDenied, ValidationError

from .assistant_intents import NUMBER, QUANTITY, TENDER, dates, quantity_value
from .assistant_tools import clarify, local_day, match_records, matches_or_clarify, product_tokens, response, table
from .finance_serializers import CheckoutInput, DiscountInput, ExpenseSerializer, qty_field
from .finance_views import SALES_ROLES, validated
from .models import AssistantProposal, Business, Customer, ExpenseCategory, Membership, Product, StockMovement, Supplier
from .reporting import as_json
from .sales import ZERO, calculate, exact_finance, get_customer, money, save_sale
from .serializers import ReceiptInput
from .services import audit, increase_stock, open_stock, receive_stock, record_expense

PROPOSAL_LIFETIME = timedelta(minutes=15)
MANAGER_ROLES = (Membership.Role.OWNER, Membership.Role.MANAGER)
UNITS = {
    "unit": {"unit", "units", "piece", "pieces", "bottle", "bottles"},
    "carton": {"carton", "cartons"}, "pack": {"pack", "packs"}, "box": {"box", "boxes"},
    "kg": {"kg", "kilogram", "kilograms"}, "litre": {"litre", "litres", "liter", "liters"},
}


class SaleProposalInput(s.Serializer):
    product = s.IntegerField(min_value=1)
    quantity = qty_field()
    discount = DiscountInput(default={"kind": "fixed", "value": ZERO})
    method = s.ChoiceField(choices=["cash", "transfer", "card", "credit"])
    customer = s.IntegerField(min_value=1, allow_null=True, default=None)
    notes = s.CharField(max_length=1000, allow_blank=True, default="")


class PurchaseProposalInput(s.Serializer):
    product = s.IntegerField(min_value=1)
    supplier = s.IntegerField(min_value=1)
    quantity = qty_field()
    unit_cost = s.DecimalField(max_digits=16, decimal_places=4, min_value=ZERO)
    received_on = s.DateField()
    reference = s.CharField(max_length=80, allow_blank=True, default="")


class OpeningProposalInput(s.Serializer):
    product = s.IntegerField(min_value=1)
    quantity = qty_field()
    unit_cost = s.DecimalField(max_digits=16, decimal_places=4, min_value=ZERO)


class AdjustmentProposalInput(s.Serializer):
    product = s.IntegerField(min_value=1)
    quantity = qty_field()
    reason = s.CharField(max_length=500)


def permit(business, user, kind, *, lock=False):
    memberships = Membership.objects.filter(business=business, user=user)
    if lock:
        memberships = memberships.select_for_update()
    membership = memberships.first()
    allowed = SALES_ROLES if kind == "sale" else MANAGER_ROLES
    if membership is None or membership.role not in allowed:
        raise PermissionDenied("Your workspace role cannot prepare or record this transaction.")


def decimal_text(value):
    if not value or not re.fullmatch(NUMBER, value):
        raise ValidationError("Enter a valid positive amount or quantity.")
    return value.replace(",", "")


def day_value(intent, business):
    day = intent.get("transaction_date") or "today"
    try:
        start, end = dates(day, local_day(business))
    except (ValueError, OverflowError):
        raise ValidationError("Use a single transaction date, such as today or 2026-11-08.") from None
    if start != end:
        raise ValidationError("Use a single transaction date.")
    return start.isoformat()


def transaction_method(intent):
    return intent.get("method", "").lower().replace("bank ", "")


def parse_proposal(business, user, intent):
    kind = intent["action"]
    permit(business, user, kind)
    method = transaction_method(intent)
    if kind == "expense":
        category, question = matches_or_clarify(
            match_records(ExpenseCategory.objects.filter(business=business), intent.get("entity", "")),
            "expense category", intent, "entity")
        if question:
            return question, None
        if not intent.get("amount"):
            return clarify("What amount was paid?", intent, "amount"), None
        if not method or method == "credit":
            return clarify("How was the expense paid?", intent, "method", ["Cash", "Bank transfer", "Card"]), None
        return None, {
            "category": category.pk, "amount": decimal_text(intent["amount"]), "incurred_on": day_value(intent, business),
            "description": intent.get("description") or category.name, "method": method,
        }

    products = Product.objects.filter(business=business, active=True)
    if kind in ("restock", "purchase", "opening", "adjustment"):
        products = products.filter(track_stock=True)
    product, question = matches_or_clarify(match_records(products, intent.get("entity", ""), catalog=True),
                                           "product", intent, "entity")
    if question:
        return question, None
    unit = intent.get("unit", "").lower()
    capacity = re.fullmatch(r"\d+\s*(?:cl|ml)", unit)
    catalog_size = (
        product.unit == "unit" and capacity
        and re.sub(r"\s+", "", unit) in product_tokens(intent["entity"]) & product_tokens(product.name)
    )
    if unit and not catalog_size and unit not in UNITS.get(product.unit, set()):
        return clarify(f"{product.name} is configured in {product.unit}. Which product or SKU has the unit you meant?",
                       {**intent, "unit": ""}, "entity"), None
    if catalog_size:
        intent = {**intent, "unit": ""}
    if not intent.get("quantity"):
        return clarify(f"How many {product.unit} of {product.name} should I use?", intent, "quantity"), None
    quantity = decimal_text(intent["quantity"])
    intent = {**intent, "entity": product.sku}
    if kind == "restock":
        return clarify(f"How should I record these {quantity} {product.unit} of {product.name}?",
                       intent, "source", ["Purchase receipt", "Opening stock", "Stock adjustment"]), None
    if kind == "opening":
        if not intent.get("unit_price"):
            return clarify(f"What was the opening cost per {product.unit}?", intent, "unit_price"), None
        return None, {"product": product.pk, "quantity": quantity, "unit_cost": decimal_text(intent["unit_price"])}
    if kind == "adjustment":
        if not intent.get("description"):
            return clarify("What is the reason for the incoming stock adjustment?", intent, "description"), None
        return None, {"product": product.pk, "quantity": quantity, "reason": intent["description"]}
    if kind == "purchase":
        supplier, question = matches_or_clarify(
            match_records(Supplier.objects.filter(business=business, active=True), intent.get("supplier", "")),
            "supplier", intent, "supplier")
        if question:
            return question, None
        if not intent.get("unit_price"):
            return clarify(f"What was the purchase cost per {product.unit}?", intent, "unit_price"), None
        return None, {
            "product": product.pk, "supplier": supplier.pk, "quantity": quantity,
            "unit_cost": decimal_text(intent["unit_price"]), "received_on": day_value(intent, business), "reference": "",
        }

    if intent.get("unit_price") and Decimal(decimal_text(intent["unit_price"])) != product.price:
        return clarify(f"The catalog price for {product.name} is {product.price} {business.currency} per {product.unit}. "
                       "Should I use that price?", intent, "use_catalog", ["Use catalog price"]), None
    if intent.get("transaction_date") and day_value(intent, business) != local_day(business).isoformat():
        return response("Checkout records sales at the time they are posted. Prepare a new sale using today’s date."), None
    if not method:
        answer = clarify("How was the sale paid?", intent, "method", ["Cash", "Bank transfer", "Card", "Credit"])
        answer["card"] = table("Matched product", ["Product", "Unit price", "On hand"],
                               [[product.name, {"money": str(product.price)},
                                 str(product.stock) if product.track_stock else "Untracked"]], "/products")
        return answer, None
    customer_id = None
    if intent.get("customer") or method == "credit":
        customer, question = matches_or_clarify(
            match_records(Customer.objects.filter(business=business, active=True), intent.get("customer", "")),
            "customer", intent, "customer")
        if question:
            return question, None
        customer_id = customer.pk
    return None, {
        "product": product.pk, "quantity": quantity, "method": method, "customer": customer_id,
        "discount": {"kind": intent.get("discount_kind") or "fixed", "value": decimal_text(intent.get("discount_value") or "0")},
        "notes": intent.get("description") or "",
    }


@exact_finance
def prepare(business, kind, payload, key, *, lock=False):
    if kind == "sale":
        data = validated(SaleProposalInput, payload)
        customer = get_customer(business, data["customer"])
        if data["method"] == "credit" and not customer:
            raise ValidationError("Select a registered customer for a credit sale.")
        sale = {"request_id": key, "customer": data["customer"], "notes": data["notes"], "discount": data["discount"],
                "lines": [{"product": data["product"], "quantity": data["quantity"],
                           "discount": {"kind": "fixed", "value": ZERO}}]}
        lines, totals = calculate(business, sale, lock=lock)
        line = lines[0]
        price = totals["total"]
        payments = [] if data["method"] == "credit" or price == 0 else [{"method": data["method"], "amount": price}]
        transaction_data = validated(CheckoutInput, {**sale, "payments": payments, "expected_total": price})
        preview = {"product": line["name"], "sku": line["sku"], "unit": line["unit"], "unit_price": str(line["price"]),
                   "quantity": str(line["quantity"]), "customer": customer.name if customer else "Walk-in",
                   "method": data["method"], "notes": data["notes"], "outstanding": str(price if not payments else ZERO),
                   **{field: str(value) for field, value in totals.items() if field != "cogs"}}
    elif kind == "purchase":
        data = validated(PurchaseProposalInput, payload)
        transaction_data = validated(ReceiptInput, {
            "request_id": key, "supplier": data["supplier"], "received_on": data["received_on"], "reference": data["reference"],
            "lines": [{"product": data["product"], "quantity": data["quantity"], "unit_cost": data["unit_cost"]}],
        }, context={"business": business})
        products = Product.objects.filter(business=business, active=True, track_stock=True, pk=data["product"])
        product = (products.select_for_update() if lock else products).first()
        supplier = transaction_data["supplier"]
        if not product or not supplier.active:
            raise ValidationError("Choose an active supplier and a stock-tracked product.")
        if product.unit not in ("kg", "litre") and data["quantity"] != data["quantity"].to_integral_value():
            raise ValidationError(f"Enter a whole quantity in {product.unit}.")
        if product.stock + data["quantity"] >= Decimal("100000000000"):
            raise ValidationError("This would exceed the supported stock balance.")
        preview = {"product": product.name, "sku": product.sku, "unit": product.unit, "supplier": supplier.name,
                   "quantity": str(data["quantity"]), "unit_cost": str(data["unit_cost"]),
                   "date": str(data["received_on"]), "reference": data["reference"],
                   "total": str(money(data["quantity"] * data["unit_cost"]))}
    elif kind in ("opening", "adjustment"):
        data = validated(OpeningProposalInput if kind == "opening" else AdjustmentProposalInput, payload)
        products = Product.objects.filter(business=business, pk=data["product"], active=True, track_stock=True)
        product = (products.select_for_update() if lock else products).first()
        if not product:
            raise ValidationError("Choose an active stock-tracked product.")
        quantity = data["quantity"]
        if product.unit not in ("kg", "litre") and quantity != quantity.to_integral_value():
            raise ValidationError(f"Enter a whole quantity in {product.unit}.")
        if product.stock + quantity >= Decimal("100000000000"):
            raise ValidationError("This would exceed the supported stock balance.")
        preview = {"product": product.name, "sku": product.sku, "unit": product.unit,
                   "quantity": str(quantity), "new_balance": str(product.stock + quantity)}
        if kind == "opening":
            if product.stock or StockMovement.objects.filter(product=product).exists():
                raise ValidationError("Opening stock is only available before the first stock movement.")
            unit_cost = data["unit_cost"]
        else:
            if product.stock <= 0 and not StockMovement.objects.filter(product=product).exists():
                raise ValidationError("Use opening stock or a purchase receipt to establish inventory cost.")
            unit_cost = product.cost
            preview["reason"] = data["reason"]
        preview.update(unit_cost=str(unit_cost), total=str(money(quantity * unit_cost)))
        transaction_data = {"product_id": data["product"], **{key: value for key, value in data.items() if key != "product"}}
    else:
        data = validated(ExpenseSerializer, payload, context={"business": business})
        category = ExpenseCategory.objects.filter(business=business, pk=data["category_id"])
        if lock:
            category = category.select_for_update()
        record = category.first()
        if not record:
            raise ValidationError("Choose an expense category in this workspace.")
        data.pop("reason", None)
        transaction_data = data
        preview = {"category": record.name, "date": str(data["incurred_on"]), "method": data["method"],
                   "description": data["description"], "total": str(data["amount"])}
        data = {**data, "category": data["category_id"]}
        del data["category_id"]
    canonical = as_json({key: str(value) if hasattr(value, "isoformat") else value for key, value in data.items()})
    return canonical, {**preview, "currency": business.currency}, transaction_data


def clarification_value(field, message, intent):
    message = message.strip().rstrip(".!?")
    if field == "source":
        choices = {"purchase": "purchase", "purchase receipt": "purchase", "opening stock": "opening",
                   "stock adjustment": "adjustment", "adjustment": "adjustment"}
        action = choices.get(message.casefold())
        return {**intent, "action": action} if action else None
    if field == "use_catalog":
        return {**intent, "unit_price": ""} if message.casefold() in ("use catalog price", "yes") else None
    if field == "method":
        if not re.fullmatch(TENDER, message, re.I):
            return None
        message = message.lower().replace("bank ", "")
    if field in ("unit_price", "quantity", "amount"):
        match = re.fullmatch(rf"(?:₦\s*)?({QUANTITY})(?:\s+(?:naira|ngn|each|units?))?", message, re.I)
        if not match:
            return None
        message = quantity_value(match[1])
    return {**intent, field: message}


def expire(proposal):
    if proposal.status == "pending" and proposal.expires_at <= timezone.now():
        proposal.status = AssistantProposal.Status.EXPIRED
        proposal.save(update_fields=["status"])


def assert_pending(proposal, revision):
    if proposal.status != "pending":
        return "This proposal is no longer pending. Prepare a new one to continue."
    if proposal.revision != revision:
        return "This preview changed. Review the latest version before continuing."
    return None


@transaction.atomic
def change_proposal(proposal, user, revision, action, payload=None):
    proposal = AssistantProposal.objects.select_for_update().get(pk=proposal.pk)
    business = Business.objects.select_for_update().get(pk=proposal.business_id)
    if action != "cancel":
        permit(business, user, proposal.kind, lock=True)
    expire(proposal)
    if action == "confirm" and proposal.status == "confirmed":
        return proposal, None
    if action == "cancel" and proposal.status == "cancelled":
        return proposal, None
    error = assert_pending(proposal, revision)
    if error:
        return proposal, error
    if action == "cancel":
        proposal.status = AssistantProposal.Status.CANCELLED
        proposal.save(update_fields=["status"])
        return proposal, None
    if action == "edit":
        canonical, preview, _ = prepare(business, proposal.kind, payload, proposal.request_id)
        proposal.payload, proposal.preview = canonical, preview
        proposal.revision += 1
        proposal.expires_at = timezone.now() + PROPOSAL_LIFETIME
        proposal.save(update_fields=["payload", "preview", "revision", "expires_at"])
        return proposal, None
    try:
        with transaction.atomic():
            _, preview, data = prepare(business, proposal.kind, proposal.payload, proposal.request_id, lock=True)
            if preview != proposal.preview:
                raise ValidationError("The transaction details changed. Prepare a fresh preview.")
            if proposal.kind == "sale":
                sale, _ = save_sale(business, user, data)
                item = Product.objects.get(business=business, pk=proposal.payload["product"])
                result = {"id": sale.pk, "total": str(sale.total), "outstanding": str(sale.balance),
                          "stock": str(item.stock) if item.track_stock else None, "link": f"/sales?sale={sale.pk}"}
            elif proposal.kind == "purchase":
                receipt, _ = receive_stock(business, user, **data)
                item = Product.objects.get(business=business, pk=proposal.payload["product"])
                result = {"id": receipt.pk, "stock": str(item.stock), "link": "/purchases"}
            elif proposal.kind in ("opening", "adjustment"):
                service = open_stock if proposal.kind == "opening" else increase_stock
                movement = service(business, user, **data)
                result = {"id": movement.pk, "stock": str(movement.balance), "link": "/inventory"}
            else:
                expense = record_expense(business, user, data)
                result = {"id": expense.pk, "total": str(expense.amount), "link": "/expenses"}
            audit(business, user, "assistant.confirmed", proposal, kind=proposal.kind, transaction_id=result["id"])
    except ValidationError as failure:
        proposal.status = AssistantProposal.Status.FAILED
        proposal.result = {"error": as_json(failure.detail)}
        proposal.save(update_fields=["status", "result"])
        return proposal, "The transaction could not be posted. Review the reason and prepare a new proposal."
    proposal.status = AssistantProposal.Status.CONFIRMED
    proposal.result = result
    proposal.save(update_fields=["status", "result"])
    return proposal, None
