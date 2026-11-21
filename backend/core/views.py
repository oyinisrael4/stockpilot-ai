import logging
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models import F, ProtectedError
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import filters, generics, mixins, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView

from . import serializers as s
from .models import Business, Category, Membership, Product, Receipt, StockMovement, Supplier, User
from .services import audit, open_stock, receive_stock


class Health(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: dict, 503: dict})
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except OperationalError:
            return Response({"status": "unavailable"}, status=503)
        return Response({"status": "ok"})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class Session(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response({"user": s.Profile(request.user).data if request.user.is_authenticated else None})


class AccountIPThrottle(SimpleRateThrottle):
    scope = "account"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


@method_decorator(csrf_protect, name="dispatch")
class AccountAction(generics.GenericAPIView):
    permission_classes = [AllowAny]
    throttle_classes = [AccountIPThrottle]
    throttle_scope = "account"

    def validated_input(self):
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class Register(AccountAction):
    serializer_class = s.RegisterInput

    @extend_schema(responses={201: s.Profile})
    def post(self, request):
        if not settings.ALLOW_REGISTRATION:
            raise PermissionDenied("Workspace registration is currently closed.")
        data = self.validated_input()
        try:
            with transaction.atomic():
                business = Business.objects.create(name=data.pop("business_name"))
                user = User.objects.create_user(**data)
                Membership.objects.create(business=business, user=user, role=Membership.Role.OWNER)
        except IntegrityError as error:
            raise ValidationError("That username or email is already registered.") from error
        login(request, user)
        return Response(s.Profile(user).data, status=201)


class Login(AccountAction):
    serializer_class = s.LoginInput

    @extend_schema(responses={200: s.Profile})
    def post(self, request):
        data = self.validated_input()
        data["username"] = data["username"].lower()
        user = authenticate(request, **data)
        if not user:
            raise ValidationError("The username or password is incorrect.")
        login(request, user)
        return Response(s.Profile(user).data)


class Logout(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=204)


class Profile(generics.RetrieveUpdateAPIView):
    serializer_class = s.Profile

    def get_object(self):
        return self.request.user


class PasswordReset(AccountAction):
    serializer_class = s.ResetRequest

    @extend_schema(responses={204: None})
    def post(self, request):
        email = self.validated_input()["email"].lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if user and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.PUBLIC_URL.rstrip('/')}/reset#uid={uid}&token={token}"
            try:
                send_mail("Reset your StockPilot AI password", f"Open this link to reset your password:\n{link}",
                          None, [user.email])
            except Exception as error:
                logging.getLogger(__name__).warning("Password reset delivery failed (%s)", type(error).__name__)
        return Response(status=204)


class PasswordResetConfirm(AccountAction):
    serializer_class = s.ResetConfirm

    @extend_schema(responses={204: None})
    @transaction.atomic
    def post(self, request):
        data = self.validated_input()
        try:
            user_id = int(urlsafe_base64_decode(data["uid"]))
            if not 0 < user_id < 2**63:
                user_id = 0
        except (TypeError, ValueError, OverflowError):
            user_id = 0
        user = User.objects.select_for_update().filter(pk=user_id, is_active=True).first()
        if not user or not default_token_generator.check_token(user, data["token"]):
            raise ValidationError("This reset link is invalid or expired.")
        s.check_password(data["password"], user)
        user.set_password(data["password"])
        user.save(update_fields=["password"])
        return Response(status=204)


class Businesses(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        memberships = Membership.objects.filter(user=request.user).select_related("business").order_by("business__name", "business_id")
        return Response([dict(s.BusinessSerializer(m.business).data, role=m.role) for m in memberships])


class TenantMixin:
    write_roles = (Membership.Role.OWNER, Membership.Role.MANAGER)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.membership = get_object_or_404(
            Membership.objects.select_related("business"), business_id=kwargs["business_id"], user=request.user
        )
        if request.method not in SAFE_METHODS and self.membership.role not in self.write_roles:
            raise PermissionDenied("Your workspace role cannot make this change.")

    @property
    def business(self):
        return self.membership.business

    def get_queryset(self):
        return super().get_queryset().filter(business_id=self.kwargs["business_id"])


class Settings(TenantMixin, generics.RetrieveUpdateAPIView):
    serializer_class = s.BusinessSerializer
    write_roles = (Membership.Role.OWNER,)

    def get_object(self):
        return self.business

    @transaction.atomic
    def perform_update(self, serializer):
        business = serializer.save()
        audit(business, self.request.user, "business.updated", business, fields=list(serializer.validated_data))


class Members(TenantMixin, generics.ListAPIView):
    queryset = Membership.objects.select_related("user").order_by("id")
    serializer_class = s.MemberSerializer
    write_roles = (Membership.Role.OWNER,)

    @extend_schema(request=s.MemberInput, responses={200: s.MemberSerializer})
    @transaction.atomic
    def post(self, request, business_id):
        serializer = s.MemberInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(username=serializer.validated_data["username"].lower(), is_active=True).first()
        if not user:
            raise ValidationError({"username": "No registered account has this username."})
        Business.objects.select_for_update().get(pk=business_id)
        existing = Membership.objects.filter(business=self.business, user=user).first()
        if existing and existing.role == Membership.Role.OWNER:
            raise ValidationError({"role": "The owner role cannot be changed here."})
        role = serializer.validated_data["role"]
        member, _ = Membership.objects.update_or_create(business=self.business, user=user, defaults={"role": role})
        audit(self.business, request.user, "member.role_set", member, role=role)
        return Response(s.MemberSerializer(member).data)


class MemberDetail(TenantMixin, generics.GenericAPIView):
    queryset = Membership.objects.all()
    serializer_class = s.MemberSerializer
    write_roles = (Membership.Role.OWNER,)

    @extend_schema(responses={204: None})
    @transaction.atomic
    def delete(self, request, business_id, member_id):
        Business.objects.select_for_update().get(pk=business_id)
        member = get_object_or_404(self.get_queryset(), pk=member_id)
        if member.role == Membership.Role.OWNER:
            raise ValidationError("The owner cannot be removed.")
        audit(self.business, request.user, "member.removed", member, user_id=member.user_id)
        member.delete()
        return Response(status=204)


class CatalogViewSet(TenantMixin, viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter]

    def perform_create(self, serializer):
        self.save_catalog_record(serializer)

    def perform_update(self, serializer):
        self.save_catalog_record(serializer)

    @transaction.atomic
    def save_catalog_record(self, serializer):
        try:
            with transaction.atomic():
                item = serializer.save(business=self.business)
        except IntegrityError as error:
            cause = getattr(error.__cause__, "diag", None)
            field = {"unique_business_sku": "sku", "unique_business_category": "name", "unique_expense_category": "name"}.get(
                getattr(cause, "constraint_name", None)
            )
            if field is None:
                raise
            raise ValidationError({field: "This value already exists in this business."}) from error
        action = "updated" if self.action in ("update", "partial_update") else "created"
        audit(self.business, self.request.user, f"{item._meta.model_name}.{action}", item,
              fields=list(serializer.validated_data))

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        action = "archived" if hasattr(instance, "active") else "deleted"
        audit(self.business, self.request.user, f"{instance._meta.model_name}.{action}", instance)
        if action == "archived":
            instance.active = False
            instance.save(update_fields=["active"])
        else:
            try:
                instance.delete()
            except ProtectedError as error:
                raise ValidationError("This category is still assigned to products.") from error


class Categories(CatalogViewSet):
    queryset = Category.objects.all()
    serializer_class = s.CategorySerializer
    search_fields = ["name"]


class Products(CatalogViewSet):
    queryset = Product.objects.select_related("category")
    serializer_class = s.ProductSerializer
    search_fields = ["name", "sku", "barcode"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ["name", "sku", "price", "stock", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in ("update", "partial_update", "destroy"):
            queryset = queryset.select_for_update(of=("self",))
        if self.action == "list":
            state = self.request.query_params.get("state", "active")
            if state in ("active", "archived"):
                queryset = queryset.filter(active=state == "active")
            if self.request.query_params.get("tracked") == "1":
                queryset = queryset.filter(track_stock=True)
            if self.request.query_params.get("low") == "1":
                queryset = queryset.filter(track_stock=True, stock__lte=F("reorder_level"))
            category = self.request.query_params.get("category")
            if category:
                if not category.isascii() or not category.isdecimal() or len(category) > 18:
                    raise ValidationError({"category": "Enter a valid category ID."})
                queryset = queryset.filter(category_id=int(category))
        return queryset


class Suppliers(CatalogViewSet):
    queryset = Supplier.objects.all()
    serializer_class = s.SupplierSerializer
    search_fields = ["name", "email", "phone"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list" and self.request.query_params.get("active") == "1":
            return queryset.filter(active=True)
        return queryset


class Movements(TenantMixin, generics.ListAPIView):
    queryset = StockMovement.objects.select_related("product")
    serializer_class = s.MovementSerializer

    @extend_schema(request=s.StockInput, responses={201: s.MovementSerializer})
    def post(self, request, business_id):
        serializer = s.StockInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        movement = open_stock(self.business, request.user, data["product"], data["quantity"], data["unit_cost"])
        return Response(s.MovementSerializer(movement).data, status=201)


class Receipts(TenantMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Receipt.objects.select_related("supplier").prefetch_related("lines__product")
    serializer_class = s.ReceiptSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        supplier = self.request.query_params.get("supplier") if self.action == "list" else None
        if supplier:
            if not supplier.isascii() or not supplier.isdecimal() or len(supplier) > 18:
                raise ValidationError({"supplier": "Enter a valid supplier ID."})
            queryset = queryset.filter(supplier_id=int(supplier))
        return queryset

    @extend_schema(request=s.ReceiptInput, responses={201: s.ReceiptSerializer, 200: s.ReceiptSerializer})
    def create(self, request, business_id):
        serializer = s.ReceiptInput(data=request.data, context={"business": self.business})
        serializer.is_valid(raise_exception=True)
        receipt, created = receive_stock(self.business, request.user, **serializer.validated_data)
        return Response(s.ReceiptSerializer(receipt).data, status=201 if created else 200)


class Overview(TenantMixin, APIView):
    @extend_schema(responses={200: dict})
    def get(self, request, business_id):
        products = Product.objects.filter(business=self.business, active=True)
        tracked = products.filter(track_stock=True)
        return Response({
            "products": products.count(),
            "tracked": tracked.count(),
            "low_stock": tracked.filter(stock__lte=F("reorder_level")).count(),
            "receipts": Receipt.objects.filter(business=self.business).count(),
            "recent_movements": s.MovementSerializer(
                StockMovement.objects.filter(business=self.business).select_related("product")[:5], many=True
            ).data,
        })
