from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers as s

from .models import Business, Category, Membership, Product, Receipt, ReceiptLine, StockMovement, Supplier, User


def check_password(password, user):
    try:
        validate_password(password, user)
    except DjangoValidationError as error:
        raise s.ValidationError({"password": error.messages}) from error


class LoginInput(s.Serializer):
    username = s.CharField(max_length=150)
    password = s.CharField(write_only=True, max_length=256, trim_whitespace=False)


class RegisterInput(LoginInput):
    confirm_password = s.CharField(write_only=True, max_length=256, trim_whitespace=False)
    username = s.CharField(max_length=150, validators=[User._meta.get_field("username").validators[0]])
    email = s.EmailField(max_length=254)
    business_name = s.CharField(max_length=120)

    def validate_username(self, value):
        return value.lower()

    def validate_email(self, value):
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("confirm_password"):
            raise s.ValidationError({"confirm_password": "Passwords do not match"})
        check_password(attrs["password"], User(username=attrs["username"], email=attrs["email"]))
        return attrs


class Profile(s.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]
        read_only_fields = ["id", "username", "email"]


class ResetRequest(s.Serializer):
    email = s.EmailField()


class ResetConfirm(s.Serializer):
    uid = s.CharField(max_length=64)
    token = s.CharField(max_length=128)
    password = s.CharField(write_only=True, max_length=256, trim_whitespace=False)


class BusinessSerializer(s.ModelSerializer):
    tax_rate = s.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False)

    class Meta:
        model = Business
        fields = ["id", "name", "currency", "timezone", "address", "receipt_footer", "tax_rate"]

    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise s.ValidationError("Enter a valid IANA timezone, such as Africa/Lagos.") from error
        return value

    def validate_currency(self, value):
        if self.instance and value != self.instance.currency and Product.objects.filter(business=self.instance).exists():
            raise s.ValidationError("Set the currency before creating products.")
        return value


class MemberInput(s.Serializer):
    username = s.CharField(max_length=150)
    role = s.ChoiceField(choices=[choice for choice in Membership.Role.choices if choice[0] != Membership.Role.OWNER])


class MemberSerializer(s.ModelSerializer):
    username = s.CharField(source="user.username")

    class Meta:
        model = Membership
        fields = ["id", "username", "role"]


class CategorySerializer(s.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class ProductSerializer(s.ModelSerializer):
    price = s.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False)
    cost = s.DecimalField(max_digits=16, decimal_places=4, min_value=0, required=False)
    reorder_level = s.DecimalField(max_digits=14, decimal_places=3, min_value=0, required=False)
    category_name = s.CharField(source="category.name", read_only=True, default=None)

    class Meta:
        model = Product
        fields = ["id", "name", "sku", "barcode", "category", "category_name", "description", "image_url",
                  "unit", "price", "cost", "stock", "reorder_level", "taxable", "track_stock", "active"]
        read_only_fields = ["stock"]

    def validate_sku(self, value):
        return value.upper()

    def validate_image_url(self, value):
        if value and not value.startswith("https://"):
            raise s.ValidationError("Use an HTTPS image URL.")
        return value

    def validate_category(self, value):
        if value and value.business_id != self.context["view"].membership.business_id:
            raise s.ValidationError("Choose a category from this business.")
        return value

    def validate(self, attrs):
        if self.instance and StockMovement.objects.filter(product=self.instance).exists():
            for field in ("unit", "track_stock", "cost"):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise s.ValidationError({field: "This field is locked after the first stock movement."})
        return attrs


class SupplierSerializer(s.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "email", "phone", "address", "active"]


class StockInput(s.Serializer):
    product = s.IntegerField(min_value=1)
    quantity = s.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    unit_cost = s.DecimalField(max_digits=16, decimal_places=4, min_value=0)


class MovementSerializer(s.ModelSerializer):
    product_name = s.CharField(source="product.name")

    class Meta:
        model = StockMovement
        fields = ["id", "product", "product_name", "kind", "quantity", "balance", "unit_cost", "created_at"]


class ReceiptInput(s.Serializer):
    request_id = s.UUIDField()
    supplier = s.IntegerField(min_value=1)
    received_on = s.DateField()
    reference = s.CharField(max_length=80, allow_blank=True, default="")
    lines = StockInput(many=True, allow_empty=False, max_length=100)

    def validate_supplier(self, value):
        supplier = Supplier.objects.filter(pk=value, business=self.context["business"]).first()
        if supplier is None:
            raise s.ValidationError("Choose a supplier from this business.")
        return supplier

    def validate_received_on(self, value):
        if value > timezone.localdate(timezone=ZoneInfo(self.context["business"].timezone)):
            raise s.ValidationError("The receipt date cannot be in the future.")
        return value


class ReceiptLineSerializer(s.ModelSerializer):
    product_name = s.CharField(source="product.name")

    class Meta:
        model = ReceiptLine
        fields = ["product", "product_name", "quantity", "unit_cost"]


class ReceiptSerializer(s.ModelSerializer):
    supplier_name = s.CharField(source="supplier.name")
    lines = ReceiptLineSerializer(many=True)

    class Meta:
        model = Receipt
        fields = ["id", "supplier", "supplier_name", "reference", "received_on", "created_at", "lines"]
