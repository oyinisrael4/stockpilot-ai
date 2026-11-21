import csv
from datetime import date

from django.db import transaction
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import finance_serializers as s
from .models import AuditEvent, Customer, Expense, ExpenseCategory, Membership, Sale, SaleReturn
from .reporting import report
from .sales import calculate, record_payment, reverse_sale, save_sale
from .services import audit, expense_values, record_expense
from .views import CatalogViewSet, TenantMixin

SALES_ROLES = (Membership.Role.OWNER, Membership.Role.MANAGER, Membership.Role.CASHIER)


def validated(serializer_class, data, **kwargs):
    serializer = serializer_class(data=data, **kwargs)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class Customers(CatalogViewSet):
    queryset = Customer.objects.all()
    serializer_class = s.CustomerSerializer
    write_roles = SALES_ROLES
    search_fields = ["name", "email", "phone"]

    def get_queryset(self):
        queryset = super().get_queryset()
        balances = Sale.objects.filter(
            business_id=self.kwargs["business_id"], customer_id=OuterRef("pk"), status=Sale.Status.COMPLETED,
        ).order_by().values("customer_id").annotate(balance=Sum(
            F("total") - F("returned") - F("paid"), output_field=DecimalField(max_digits=32, decimal_places=2)
        )).values("balance")
        if self.action == "list" and self.request.query_params.get("active") == "1":
            queryset = queryset.filter(active=True)
        precision = DecimalField(max_digits=32, decimal_places=2)
        return queryset.annotate(balance=Coalesce(Subquery(balances, output_field=precision), Value(0), output_field=precision))


class Sales(TenantMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Sale.objects.prefetch_related("lines", "payments", "returns__lines__sale_line")
    serializer_class = s.SaleSerializer
    write_roles = SALES_ROLES
    filter_backends = [filters.SearchFilter]
    search_fields = ["customer_name", "notes"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            state = self.request.query_params.get("status")
            customer = self.request.query_params.get("customer")
            if state:
                queryset = queryset.filter(status=state)
            if customer:
                if not customer.isascii() or not customer.isdecimal() or len(customer) > 18:
                    raise ValidationError({"customer": "Enter a valid customer ID."})
                queryset = queryset.filter(customer_id=int(customer))
        return queryset

    @extend_schema(request=s.QuoteInput, responses={200: dict})
    @action(detail=False, methods=["post"])
    def quote(self, request, business_id):
        lines, totals = calculate(self.business, validated(s.QuoteInput, request.data))
        return Response({
            **{field: str(value) for field, value in totals.items() if field != "cogs"},
            "lines": [{"product": line["product"].pk, **{field: str(line[field]) for field in ("subtotal", "discount", "tax", "total")}} for line in lines],
        })

    @extend_schema(request=s.DraftInput, responses={200: s.SaleSerializer})
    @action(detail=False, methods=["post"])
    def draft(self, request, business_id):
        sale, _ = save_sale(self.business, request.user, validated(s.DraftInput, request.data), draft=True)
        return Response(self.get_serializer(sale).data)

    @extend_schema(request=s.CheckoutInput, responses={201: s.SaleSerializer, 200: s.SaleSerializer})
    @action(detail=False, methods=["post"])
    def checkout(self, request, business_id):
        sale, created = save_sale(self.business, request.user, validated(s.CheckoutInput, request.data))
        return Response(self.get_serializer(sale).data, status=201 if created else 200)

    @extend_schema(request=s.AdditionalPayment, responses={200: s.SaleSerializer})
    @action(detail=True, methods=["post"], url_path="record-payment")
    def payment(self, request, business_id, pk):
        sale = self.get_object()
        sale = record_payment(self.business, request.user, sale.pk, validated(s.AdditionalPayment, request.data))
        return Response(self.get_serializer(sale).data)

    def reversal(self, request, *, void=False, preview=False):
        if self.membership.role not in (Membership.Role.OWNER, Membership.Role.MANAGER):
            raise PermissionDenied("Only owners and managers can reverse sales.")
        sale = self.get_object()
        data = validated(s.VoidInput if void else s.ReturnInput, request.data)
        result = reverse_sale(self.business, request.user, sale.pk, data, void=void, preview=preview)
        if preview:
            return Response(result)
        reversal, created = result
        return Response(s.ReturnSerializer(reversal).data, status=201 if created else 200)

    @extend_schema(request=s.ReturnInput, responses={200: dict})
    @action(detail=True, methods=["post"], url_path="return-quote")
    def return_quote(self, request, business_id, pk):
        return self.reversal(request, preview=True)

    @extend_schema(request=s.VoidInput, responses={200: dict})
    @action(detail=True, methods=["post"], url_path="void-quote")
    def void_quote(self, request, business_id, pk):
        return self.reversal(request, void=True, preview=True)

    @extend_schema(request=s.ReturnInput, responses={201: s.ReturnSerializer, 200: s.ReturnSerializer})
    @action(detail=True, methods=["post"], url_path="return")
    def return_sale(self, request, business_id, pk):
        return self.reversal(request)

    @extend_schema(request=s.VoidInput, responses={201: s.ReturnSerializer, 200: s.ReturnSerializer})
    @action(detail=True, methods=["post"])
    def void(self, request, business_id, pk):
        return self.reversal(request, void=True)


class Returns(TenantMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = SaleReturn.objects.prefetch_related("lines__sale_line")
    serializer_class = s.ReturnSerializer


class ExpenseCategories(CatalogViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = s.ExpenseCategorySerializer
    search_fields = ["name"]


class Expenses(TenantMixin, mixins.ListModelMixin, mixins.CreateModelMixin,
               mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Expense.objects.select_related("category")
    serializer_class = s.ExpenseSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["description", "category__name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in ("partial_update", "update", "void"):
            queryset = queryset.select_for_update(of=("self",))
        if self.action == "list":
            for parameter, lookup in [("start", "incurred_on__gte"), ("end", "incurred_on__lte")]:
                value = self.request.query_params.get(parameter)
                if value:
                    try:
                        parsed = parse_date(value)
                    except ValueError:
                        parsed = None
                    if not isinstance(parsed, date):
                        raise ValidationError({parameter: "Enter a valid date."})
                    queryset = queryset.filter(**{lookup: parsed})
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.validated_data.pop("reason", None)
        serializer.instance = record_expense(self.business, self.request.user, serializer.validated_data)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        before = expense_values(serializer.instance)
        reason = serializer.validated_data.pop("reason")
        expense = serializer.save()
        audit(self.business, self.request.user, "expense.corrected", expense, reason=reason,
              before=before, after=expense_values(expense))

    @extend_schema(request=s.ReasonInput, responses={200: s.ExpenseSerializer})
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def void(self, request, business_id, pk):
        expense = self.get_object()
        reason = validated(s.ReasonInput, request.data)["reason"]
        if not expense.voided:
            expense.voided = True
            expense.save(update_fields=["voided"])
            audit(self.business, request.user, "expense.voided", expense, reason=reason)
        return Response(self.get_serializer(expense).data)

    @extend_schema(responses={200: dict})
    @action(detail=True, methods=["get"])
    def history(self, request, business_id, pk):
        expense = self.get_object()
        events = AuditEvent.objects.filter(business=self.business, target_id=expense.pk, action__startswith="expense.")
        return Response(list(events.order_by("-id").values("action", "created_at", "details", "actor__username")))


class Reports(TenantMixin, APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "business_reports"
    @extend_schema(parameters=[s.ReportInput], responses={200: dict})
    def get(self, request, business_id):
        return Response(report(self.business, **validated(s.ReportInput, request.query_params)))


class ReportCsv(TenantMixin, APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "business_reports"
    @extend_schema(parameters=[s.ReportInput], responses={200: str})
    def get(self, request, business_id):
        result = report(self.business, **validated(s.ReportInput, request.query_params))
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="stockpilot-financial-report.csv"'
        writer = csv.writer(response)
        writer.writerow(["Metric", "Selected period", "Comparison period"])
        for key, value in result["current"]["totals"].items():
            writer.writerow([key.replace("_", " "), value, result["comparison"]["totals"][key] if result["comparison"] else ""])
        writer.writerow(["Current receivables", result["outstanding"]])
        writer.writerow(["Current inventory valuation", result["inventory"]["valuation"]])
        writer.writerow([])
        writer.writerow(["Bucket start", "Net sales", "Operating expenses"])
        for point in result["current"]["series"]:
            writer.writerow([point["date"], point["net_sales"], point["operating_expenses"]])
        return response
