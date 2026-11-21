from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek

from .models import Expense, Product, ReturnLine, Sale, SaleLine, SaleReturn
from .sales import ZERO, exact_finance, money

WIDE = DecimalField(max_digits=40, decimal_places=7)


def summed(queryset, **fields):
    values = queryset.aggregate(**{key: Sum(value, default=ZERO, output_field=WIDE) for key, value in fields.items()})
    return {key: money(value) for key, value in values.items()}


def as_json(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [as_json(item) for item in value]
    if isinstance(value, dict):
        return {key: as_json(item) for key, item in value.items()}
    return value


def bucket(day, group):
    if group == "week":
        return day - timedelta(days=day.weekday())
    if group == "month":
        return day.replace(day=1)
    return day


@exact_finance
def period(business, start, end, group):
    zone = ZoneInfo(business.timezone)
    lower = datetime.combine(start, time.min, zone)
    upper = datetime.combine(end + timedelta(days=1), time.min, zone)
    sales = Sale.objects.filter(business=business, posted_at__gte=lower, posted_at__lt=upper)
    returns = SaleReturn.objects.filter(business=business, sale__posted_at__isnull=False, created_at__gte=lower, created_at__lt=upper)
    expenses = Expense.objects.filter(business=business, voided=False, incurred_on__range=(start, end))
    totals = summed(sales, gross_sales="subtotal", discounts="discount", sales_tax="tax", cogs="cogs")
    reversal = summed(returns, sales_returns=F("total") - F("tax"), refunds="refund", reversed_cogs="cogs_reversed", reversed_tax="tax")
    expense_total = summed(expenses, operating_expenses="amount")["operating_expenses"]
    revenue = totals["gross_sales"] - totals["discounts"] - reversal["sales_returns"]
    cogs = totals["cogs"] - reversal["reversed_cogs"]
    profit = revenue - cogs
    totals.update(sale_count=sales.count(), sales_returns=reversal["sales_returns"],
                  refunds=reversal["refunds"], sales_tax=totals["sales_tax"] - reversal["reversed_tax"],
                  net_sales=revenue, cogs=cogs, gross_profit=profit, operating_expenses=expense_total,
                  operating_result=profit - expense_total, gross_margin=money(100 * profit / revenue) if revenue > 0 else None)

    groups = defaultdict(lambda: {"net_sales": ZERO, "operating_expenses": ZERO})
    for offset in range((end - start).days + 1):
        groups[bucket(start + timedelta(days=offset), group)]
    trunc = {"day": TruncDay, "week": TruncWeek, "month": TruncMonth}[group]
    for queryset, field, expression, sign in (
        (sales, "posted_at", F("subtotal") - F("discount"), 1),
        (returns, "created_at", F("total") - F("tax"), -1),
    ):
        series = queryset.order_by().annotate(bucket=trunc(field, tzinfo=zone)).values("bucket").annotate(
            amount=Sum(expression, output_field=WIDE))
        for row in series:
            groups[row["bucket"].date()]["net_sales"] += sign * money(row["amount"])
    for row in expenses.order_by().values("incurred_on").annotate(amount=Sum("amount", output_field=WIDE)):
        groups[bucket(row["incurred_on"], group)]["operating_expenses"] += money(row["amount"])

    expense_groups = expenses.order_by().values("category_id", "category__name").annotate(
        amount=Sum("amount", output_field=WIDE), count=Count("id")).order_by("-amount", "category_id")
    return {
        "start": start.isoformat(), "end": end.isoformat(), "totals": totals,
        "series": [{"date": day.isoformat(), **values} for day, values in sorted(groups.items())],
        "expense_categories": [{"name": row["category__name"], "amount": money(row["amount"]), "count": row["count"]} for row in expense_groups],
    }


@exact_finance
def report(business, start, end, group, compare_start=None, compare_end=None):
    current = period(business, start, end, group)
    comparison = period(business, compare_start, compare_end, group) if compare_start else None
    products = Product.objects.filter(business=business, active=True, track_stock=True)
    zone = ZoneInfo(business.timezone)
    lower = datetime.combine(start, time.min, zone)
    upper = datetime.combine(end + timedelta(days=1), time.min, zone)
    sold = SaleLine.objects.filter(business=business, sale__posted_at__gte=lower, sale__posted_at__lt=upper)
    returned = ReturnLine.objects.filter(business=business, sale_return__created_at__gte=lower, sale_return__created_at__lt=upper)
    units = defaultdict(lambda: ZERO)
    for row in sold.order_by().values("product_id").annotate(units=Sum("quantity", output_field=WIDE)):
        units[row["product_id"]] += row["units"]
    for row in returned.order_by().values("sale_line__product_id").annotate(units=Sum("quantity", output_field=WIDE)):
        units[row["sale_line__product_id"]] -= row["units"]
    activity = [{"id": row["id"], "name": row["name"], "unit": row["unit"], "units": units[row["id"]]}
                for row in Product.objects.filter(business=business).filter(active=True).values("id", "name", "unit")]
    slow = sorted(activity, key=lambda row: (row["units"], row["name"], row["id"]))[:5]
    top = sorted((row for row in activity if row["units"] > 0), key=lambda row: (-row["units"], row["name"], row["id"]))[:5]
    return as_json({
        "current": current, "comparison": comparison,
        "inventory": {
            **summed(products, valuation=F("stock") * F("cost")),
            "low_stock_count": products.filter(stock__lte=F("reorder_level")).count(),
            "low_stock": list(products.filter(stock__lte=F("reorder_level")).order_by("stock", "id").values("id", "name", "stock", "reorder_level", "unit")[:10]),
        },
        "outstanding": summed(Sale.objects.filter(business=business, status=Sale.Status.COMPLETED),
                              receivables=F("total") - F("returned") - F("paid"))["receivables"],
        "top_products": top, "slow_products": slow,
    })
