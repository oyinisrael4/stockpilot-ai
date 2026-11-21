import uuid
from decimal import localcontext

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    email = models.EmailField(unique=True)


class Business(models.Model):
    name = models.CharField(max_length=120)
    currency = models.CharField(max_length=3, choices=[("NGN", "Nigerian naira"), ("USD", "US dollar"), ("GBP", "British pound"), ("EUR", "Euro")], default="NGN")
    timezone = models.CharField(max_length=64, default="Africa/Lagos")
    address = models.CharField(max_length=250, blank=True)
    receipt_footer = models.CharField(max_length=250, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"
        ANALYST = "analyst", "Analyst"
        VIEWER = "viewer", "Viewer"

    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=Role.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["business", "user"], name="unique_business_member")]


class BusinessRecord(models.Model):
    business = models.ForeignKey(Business, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Category(BusinessRecord):
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["business", "name"], name="unique_business_category")]


class Product(BusinessRecord):
    class Unit(models.TextChoices):
        UNIT = "unit", "Unit"
        PACK = "pack", "Pack"
        CARTON = "carton", "Carton"
        BOX = "box", "Box"
        KG = "kg", "Kilogram"
        LITRE = "litre", "Litre"

    name = models.CharField(max_length=150)
    sku = models.CharField(max_length=64)
    barcode = models.CharField(max_length=64, blank=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.PROTECT)
    description = models.TextField(blank=True, max_length=2000)
    image_url = models.URLField(max_length=500, blank=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.UNIT)
    price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reorder_level = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    taxable = models.BooleanField(default=False)
    track_stock = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["business", "active", "name", "id"], name="product_catalog_order")]
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["business", "sku"], name="unique_business_sku"),
            models.CheckConstraint(condition=Q(price__gte=0, cost__gte=0, stock__gte=0, reorder_level__gte=0), name="nonnegative_product_values"),
        ]


class Supplier(BusinessRecord):
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=250, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]


class Receipt(BusinessRecord):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    reference = models.CharField(max_length=80, blank=True)
    received_on = models.DateField()
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    request_id = models.UUIDField(default=uuid.uuid4)
    fingerprint = models.CharField(max_length=64)

    class Meta:
        ordering = ["-received_on", "-id"]
        constraints = [models.UniqueConstraint(fields=["business", "request_id"], name="unique_receipt_request")]


class ReceiptLine(BusinessRecord):
    receipt = models.ForeignKey(Receipt, related_name="lines", on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=16, decimal_places=4)


class StockMovement(BusinessRecord):
    class Kind(models.TextChoices):
        OPENING = "opening", "Opening stock"
        PURCHASE = "purchase", "Purchase receipt"
        SALE = "sale", "Sale"
        RETURN = "return", "Sale return"
        VOID = "void", "Sale void"
        ADJUSTMENT = "adjustment", "Stock adjustment"

    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    balance = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=16, decimal_places=4)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    receipt_line = models.OneToOneField(ReceiptLine, null=True, on_delete=models.PROTECT)
    sale_line = models.ForeignKey("SaleLine", null=True, on_delete=models.PROTECT)
    return_line = models.OneToOneField("ReturnLine", null=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["product"], condition=Q(kind="opening"), name="one_opening_per_product")]


class AuditEvent(BusinessRecord):
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=48)
    target_id = models.PositiveBigIntegerField()
    details = models.JSONField(default=dict)


class Customer(BusinessRecord):
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=250, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]


class Tender(models.TextChoices):
    CASH = "cash", "Cash"
    TRANSFER = "transfer", "Bank transfer"
    CARD = "card", "Card"


class Sale(BusinessRecord):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"
        VOIDED = "voided", "Voided"

    customer = models.ForeignKey(Customer, null=True, on_delete=models.PROTECT)
    customer_name = models.CharField(max_length=150, blank=True)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    posted_at = models.DateTimeField(null=True)
    notes = models.CharField(max_length=1000, blank=True)
    draft = models.JSONField(default=dict)
    request_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64, blank=True)
    subtotal = models.DecimalField(max_digits=32, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=32, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=32, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=32, decimal_places=2, default=0)
    cogs = models.DecimalField(max_digits=32, decimal_places=2, default=0)
    returned = models.DecimalField(max_digits=32, decimal_places=2, default=0)
    paid = models.DecimalField(max_digits=32, decimal_places=2, default=0)

    @property
    def balance(self):
        with localcontext() as context:
            context.prec = 60
            return self.total - self.returned - self.paid

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["business", "posted_at"])]
        constraints = [
            models.UniqueConstraint(fields=["business", "request_id"], name="unique_sale_request"),
            models.CheckConstraint(condition=Q(returned__gte=0, paid__gte=0, total__gte=models.F("returned") + models.F("paid")), name="valid_sale_balance"),
        ]


class SaleLine(BusinessRecord):
    sale = models.ForeignKey(Sale, related_name="lines", on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    sku = models.CharField(max_length=64)
    unit = models.CharField(max_length=10)
    tracked = models.BooleanField()
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=16, decimal_places=4)
    subtotal = models.DecimalField(max_digits=32, decimal_places=2)
    discount = models.DecimalField(max_digits=32, decimal_places=2)
    tax = models.DecimalField(max_digits=32, decimal_places=2)
    total = models.DecimalField(max_digits=32, decimal_places=2)
    cogs = models.DecimalField(max_digits=32, decimal_places=2)
    returned_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    class Meta:
        ordering = ["id"]
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0, returned_quantity__gte=0, returned_quantity__lte=models.F("quantity")), name="valid_returned_quantity")]


class SalePayment(BusinessRecord):
    sale = models.ForeignKey(Sale, related_name="payments", on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    method = models.CharField(max_length=10, choices=Tender.choices)
    amount = models.DecimalField(max_digits=32, decimal_places=2)
    request_id = models.UUIDField(null=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="positive_sale_payment"),
            models.UniqueConstraint(fields=["business", "request_id"], name="unique_payment_request"),
        ]


class SaleReturn(BusinessRecord):
    sale = models.ForeignKey(Sale, related_name="returns", on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    request_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    reason = models.CharField(max_length=500)
    void = models.BooleanField(default=False)
    refund_method = models.CharField(max_length=10, choices=Tender.choices, blank=True)
    refund = models.DecimalField(max_digits=32, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=32, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=32, decimal_places=2, default=0)
    cogs_reversed = models.DecimalField(max_digits=32, decimal_places=2, default=0)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["business", "created_at"])]
        constraints = [models.UniqueConstraint(fields=["business", "request_id"], name="unique_return_request")]


class ReturnLine(BusinessRecord):
    sale_return = models.ForeignKey(SaleReturn, related_name="lines", on_delete=models.PROTECT)
    sale_line = models.ForeignKey(SaleLine, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    restocked = models.BooleanField(default=False)
    total = models.DecimalField(max_digits=32, decimal_places=2)
    tax = models.DecimalField(max_digits=32, decimal_places=2)
    cogs_reversed = models.DecimalField(max_digits=32, decimal_places=2)

    class Meta:
        ordering = ["id"]


class ExpenseCategory(BusinessRecord):
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["business", "name"], name="unique_expense_category")]


class Expense(BusinessRecord):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    incurred_on = models.DateField()
    description = models.CharField(max_length=500)
    method = models.CharField(max_length=10, choices=Tender.choices)
    voided = models.BooleanField(default=False)

    class Meta:
        ordering = ["-incurred_on", "-id"]
        indexes = [models.Index(fields=["business", "incurred_on"])]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="positive_expense")]


class AssistantConversation(BusinessRecord):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=90, default="New conversation")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["business", "user", "-updated_at"])]


class AssistantExchange(BusinessRecord):
    conversation = models.ForeignKey(AssistantConversation, related_name="exchanges", on_delete=models.CASCADE)
    request_id = models.UUIDField()
    prompt = models.CharField(max_length=2000)
    answer = models.JSONField()

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["conversation", "request_id"], name="unique_assistant_message_request")]


class AssistantProposal(BusinessRecord):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"
        FAILED = "failed", "Failed"

    class Kind(models.TextChoices):
        SALE = "sale", "Sale"
        EXPENSE = "expense", "Expense"
        PURCHASE = "purchase", "Purchase"
        OPENING = "opening", "Opening stock"
        ADJUSTMENT = "adjustment", "Stock adjustment"

    exchange = models.OneToOneField(AssistantExchange, related_name="proposal", on_delete=models.CASCADE)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    request_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    revision = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField()
    payload = models.JSONField()
    preview = models.JSONField()
    result = models.JSONField(default=dict)
