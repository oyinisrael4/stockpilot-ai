from decimal import Decimal
from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework import serializers as s

from .models import Customer, Expense, ExpenseCategory, ReturnLine, Sale, SaleLine, SalePayment, SaleReturn, Tender


def money_field(**kwargs):
    return s.DecimalField(max_digits=32, decimal_places=2, min_value=Decimal("0"), **kwargs)


def qty_field():
    return s.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal(".001"))


class DiscountInput(s.Serializer):
    kind = s.ChoiceField(choices=["fixed", "percent"])
    value = money_field()

    def validate(self, attrs):
        if attrs["kind"] == "percent" and attrs["value"] > 100:
            raise s.ValidationError("Percentage discounts must be between 0 and 100.")
        return attrs


class SaleItem(s.Serializer):
    product = s.IntegerField(min_value=1)
    quantity = qty_field()
    discount = DiscountInput(default={"kind": "fixed", "value": Decimal("0.00")})


class PaymentInput(s.Serializer):
    method = s.ChoiceField(choices=Tender.choices)
    amount = s.DecimalField(max_digits=32, decimal_places=2, min_value=Decimal(".01"))


class AdditionalPayment(PaymentInput):
    request_id = s.UUIDField()


class QuoteInput(s.Serializer):
    lines = SaleItem(many=True, allow_empty=False, max_length=100)
    discount = DiscountInput(default={"kind": "fixed", "value": Decimal("0.00")})


class DraftInput(QuoteInput):
    request_id = s.UUIDField()
    customer = s.IntegerField(min_value=1, allow_null=True, default=None)
    notes = s.CharField(max_length=1000, allow_blank=True, default="")
    payments = PaymentInput(many=True, max_length=10, default=list)


class CheckoutInput(DraftInput):
    expected_total = money_field()


class VoidInput(s.Serializer):
    request_id = s.UUIDField()
    reason = s.CharField(max_length=500)
    expected_refund = money_field()
    refund_method = s.ChoiceField(choices=Tender.choices, allow_blank=True, default="")


class ReturnItem(s.Serializer):
    sale_line = s.IntegerField(min_value=1)
    quantity = qty_field()
    restocked = s.BooleanField(default=True)


class ReturnInput(VoidInput):
    lines = ReturnItem(many=True, allow_empty=False, max_length=100)


class PaymentSerializer(s.ModelSerializer):
    class Meta:
        model = SalePayment
        fields = ["id", "method", "amount", "created_at"]


class LineSerializer(s.ModelSerializer):
    class Meta:
        model = SaleLine
        fields = ["id", "product", "name", "sku", "unit", "tracked", "quantity", "price",
                  "subtotal", "discount", "tax", "total", "returned_quantity"]


class ReturnLineSerializer(s.ModelSerializer):
    name = s.CharField(source="sale_line.name")

    class Meta:
        model = ReturnLine
        fields = ["sale_line", "name", "quantity", "restocked", "total", "tax"]


class ReturnSerializer(s.ModelSerializer):
    lines = ReturnLineSerializer(many=True)

    class Meta:
        model = SaleReturn
        fields = ["id", "sale", "created_at", "reason", "void", "refund_method", "refund", "total", "tax", "lines"]


class SaleSerializer(s.ModelSerializer):
    balance = s.DecimalField(max_digits=32, decimal_places=2, read_only=True)
    lines = LineSerializer(many=True)
    payments = PaymentSerializer(many=True)
    returns = ReturnSerializer(many=True)

    class Meta:
        model = Sale
        fields = ["id", "request_id", "status", "created_at", "posted_at", "customer", "customer_name", "notes",
                  "subtotal", "discount", "tax", "total", "paid", "returned", "balance", "lines", "payments", "returns", "draft"]


class CustomerSerializer(s.ModelSerializer):
    balance = s.DecimalField(max_digits=32, decimal_places=2, read_only=True, default=0)

    class Meta:
        model = Customer
        fields = ["id", "name", "email", "phone", "address", "active", "balance"]


class ExpenseCategorySerializer(s.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name"]


class ExpenseSerializer(s.ModelSerializer):
    amount = s.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal(".01"))
    category_name = s.CharField(source="category.name", read_only=True)
    category = s.IntegerField(source="category_id", min_value=1)
    reason = s.CharField(write_only=True, required=False, max_length=500)

    class Meta:
        model = Expense
        fields = ["id", "category", "category_name", "amount", "incurred_on", "description", "method", "voided", "reason"]
        read_only_fields = ["voided"]

    @property
    def business(self):
        return self.context["business"] if "business" in self.context else self.context["view"].business

    def validate_category(self, value):
        if not ExpenseCategory.objects.filter(business=self.business, pk=value).exists():
            raise s.ValidationError("Choose an expense category in this workspace.")
        return value

    def validate_incurred_on(self, value):
        zone = ZoneInfo(self.business.timezone)
        if value > timezone.localdate(timezone=zone):
            raise s.ValidationError("Choose today or an earlier expense date.")
        return value

    def validate(self, attrs):
        if self.instance and (self.instance.voided or not attrs.get("reason")):
            raise s.ValidationError("An active expense and a correction reason are required.")
        return attrs


class ReasonInput(s.Serializer):
    reason = s.CharField(max_length=500)


class ReportInput(s.Serializer):
    start = s.DateField()
    end = s.DateField()
    compare_start = s.DateField(required=False)
    compare_end = s.DateField(required=False)
    group = s.ChoiceField(choices=["day", "week", "month"], default="day")

    def validate(self, attrs):
        if ("compare_start" in attrs) != ("compare_end" in attrs):
            raise s.ValidationError("Provide both comparison dates.")
        ranges = [(attrs["start"], attrs["end"])]
        if "compare_start" in attrs:
            ranges.append((attrs["compare_start"], attrs["compare_end"]))
        if any(not (0 <= (end - start).days <= 730) or start.year < 1901 or end.year > 9998 for start, end in ranges):
            raise s.ValidationError("Choose ordered dates between 1901 and 9998 spanning at most 731 days.")
        return attrs
