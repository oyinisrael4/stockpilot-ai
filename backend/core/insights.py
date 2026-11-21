"""Read-only decision support. All figures use Decimal and workspace-scoped records."""
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import ROUND_CEILING, Decimal
from statistics import median
from zoneinfo import ZoneInfo

from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import Expense, Product, ReturnLine, Sale, SaleLine, SalePayment
from .reporting import WIDE, as_json, period
from .sales import ZERO, exact_finance, money


METRICS = {
    "sale_count": "Posted sales", "net_sales": "Net sales", "gross_profit": "Gross profit",
    "operating_expenses": "Operating expenses", "operating_result": "Operating result",
}


def bounds(start, end, zone):
    return datetime.combine(start, time.min, zone), datetime.combine(end + timedelta(days=1), time.min, zone)


def product_activity(business, start, end, zone):
    lower, upper = bounds(start, end, zone)
    sold = SaleLine.objects.filter(business=business, product__business=business, sale__business=business,
                                   sale__posted_at__gte=lower, sale__posted_at__lt=upper)
    refunds = ReturnLine.objects.filter(business=business, sale_line__business=business,
                                       sale_line__product__business=business, sale_return__business=business,
                                       sale_return__created_at__gte=lower, sale_return__created_at__lt=upper)
    rows = defaultdict(lambda: {"units": ZERO, "revenue": ZERO, "cogs": ZERO, "selling_days": 0})
    for source, key, revenue, cost, direction in (
        (sold, "product_id", F("subtotal") - F("discount"), F("cogs"), 1),
        (refunds, "sale_line__product_id", F("total") - F("tax"), F("cogs_reversed"), -1),
    ):
        grouped = source.order_by().values(key).annotate(
            units=Sum("quantity", output_field=WIDE), revenue=Sum(revenue, output_field=WIDE),
            cogs=Sum(cost, output_field=WIDE))
        if direction == 1:
            grouped = grouped.annotate(selling_days=Count(TruncDate("sale__posted_at", tzinfo=zone), distinct=True))
        for row in grouped:
            item = rows[row[key]]
            for field in ("units", "revenue", "cogs"):
                item[field] += direction * row[field]
            item["selling_days"] += row.get("selling_days", 0)
    return rows


def customer_activity(business, start, end, today, zone):
    lower, upper = bounds(start, end, zone)
    sales = Sale.objects.filter(business=business, customer__business=business, status=Sale.Status.COMPLETED)
    balance = F("total") - F("returned") - F("paid")
    summary = sales.order_by().values("customer_id", "customer__name").annotate(
        outstanding=Sum(balance, output_field=WIDE),
        oldest=Min("posted_at", filter=Q(total__gt=F("returned") + F("paid"))),
        open_invoices=Count("id", filter=Q(total__gt=F("returned") + F("paid"))),
        period_sales=Count("id", filter=Q(posted_at__gte=lower, posted_at__lt=upper)),
    ).order_by("-outstanding", "customer_id")
    payments = SalePayment.objects.filter(business=business, sale__business=business, sale__customer__business=business,
                                          sale__status=Sale.Status.COMPLETED, created_at__gte=lower, created_at__lt=upper)
    collected = {row["sale__customer_id"]: row for row in payments.order_by().values("sale__customer_id").annotate(
        receipts=Sum("amount", output_field=WIDE), later_payments=Count("id", filter=Q(request_id__isnull=False)),
        latest_payment=Max("created_at"))}
    rows = []
    for item in summary.iterator():
        payment = collected.get(item["customer_id"], {})
        if item["outstanding"] <= 0 and not item["period_sales"] and not payment:
            continue
        oldest = item["oldest"]
        rows.append({"id": item["customer_id"], "name": item["customer__name"], "outstanding": money(item["outstanding"]),
                     "open_invoices": item["open_invoices"], "age": max(0, (today - oldest.astimezone(zone).date()).days) if oldest else None,
                     "payments": money(payment.get("receipts", ZERO)), "later_payments": payment.get("later_payments", 0),
                     "latest_payment": payment["latest_payment"].astimezone(zone).date().isoformat() if payment else None})
    return rows


def forecast(business, today):
    # Use complete Monday–Sunday weeks to avoid partial-week bias.
    week = today - timedelta(days=today.weekday())
    start, end = week - timedelta(weeks=8), week - timedelta(days=1)
    history = period(business, start, end, "week")["series"]
    values = [row["net_sales"] for row in history]
    if sum(value > 0 for value in values) < 6 or min(values) < 0:
        return {"available": False, "note": "A forecast needs eight complete weeks with positive net sales in at least six and no negative weeks."}
    return {"available": True, "start": week.isoformat(), "end": (week + timedelta(days=6)).isoformat(),
            "history_start": start.isoformat(), "history_end": end.isoformat(), "estimate": money(median(values)), "history": history,
            "low": min(values), "high": max(values), "note": "Median of eight complete weeks. The range is the observed low to high, with no probability guarantee. It assumes recent conditions persist and does not account for seasonality or known changes."}


def compare_periods(current, previous):
    return [{"label": label, "key": key, "current": current[key], "previous": previous[key],
             "delta": current[key] - previous[key],
             "percent": money(Decimal(100) * (current[key] - previous[key]) / previous[key]) if previous[key] > 0 else None}
            for key, label in METRICS.items()]


@exact_finance
def insights(business, start, end, group="day", compare_start=None, compare_end=None):
    if compare_start is None:
        compare_end = start - timedelta(days=1)
        compare_start = compare_end - (end - start)
    zone = ZoneInfo(business.timezone)
    today = timezone.localdate(timezone=zone)
    current = period(business, start, end, group)
    previous = period(business, compare_start, compare_end, group)
    now, before = current["totals"], previous["totals"]
    metrics = compare_periods(now, before)
    products = product_activity(business, start, end, zone)
    prior_products = product_activity(business, compare_start, compare_end, zone)
    velocity = product_activity(business, today - timedelta(days=28), today - timedelta(days=1), zone)
    ranked, low, slow, recommendations = [], [], [], []

    def recommendation(key, priority, title, evidence, action, link, estimate=None):
        recommendations.append(dict(key=key, priority=priority, title=title, evidence=evidence,
                                    action=action, link=link, estimate=estimate))

    for product in Product.objects.filter(business=business).order_by("id").iterator():
        row = {"name": product.name, "sku": product.sku, "units": products[product.id]["units"],
               "revenue": money(products[product.id]["revenue"]),
               "profit": money(products[product.id]["revenue"] - products[product.id]["cogs"]),
               "previous_revenue": money(prior_products[product.id]["revenue"])}
        if any(value != ZERO for key, value in row.items() if key not in ("name", "sku")):
            ranked.append(row)
        if not product.active or not product.track_stock:
            continue
        days_listed = (today - product.created_at.astimezone(zone).date()).days
        recent = velocity[product.id]
        if product.stock <= product.reorder_level:
            enough = days_listed >= 28 and recent["selling_days"] >= 4 and recent["units"] > 0
            demand = max(ZERO, recent["units"]) / 28
            target = max(product.reorder_level, demand * 14)
            suggested = max(ZERO, target - product.stock).quantize(
                Decimal("0.001") if product.unit in ("kg", "litre") else Decimal("1"), rounding=ROUND_CEILING) if enough else None
            low.append({**row, "stock": product.stock, "reorder_at": product.reorder_level, "unit": product.unit,
                        "recent_units": recent["units"], "selling_days": recent["selling_days"], "suggested": suggested})
        if product.stock > 0 and days_listed >= 28 and recent["selling_days"] <= 1:
            slow.append({**row, "stock": product.stock, "unit": product.unit, "recent_units": recent["units"],
                         "selling_days": recent["selling_days"]})
    low.sort(key=lambda row: (row["stock"] > 0, row["stock"] - row["reorder_at"], row["sku"]))
    slow.sort(key=lambda row: (row["selling_days"], -row["stock"], row["sku"]))
    # A quiet store provides weak evidence about individual product movement.
    active_days = sum(row["net_sales"] > 0 for row in period(business, today - timedelta(days=28),
                                                             today - timedelta(days=1), "day")["series"])
    if active_days < 7:
        slow = []
    for row in low[:3]:
        recommendation("stock-" + row["sku"], 1 if row["stock"] <= 0 else 2, f'Review stock for {row["name"]}',
                       f'On hand {row["stock"]} {row["unit"]}. Reorder level {row["reorder_at"]}.',
                       "Check open purchases and supplier lead time", "/inventory?low=1",
                       f'Estimated reorder {row["suggested"]} {row["unit"]} using 14 days of recent demand or the reorder level, whichever is higher.'
                       if row["suggested"] is not None else None)
    if slow:
        row = slow[0]
        recommendation("slow", 3, f'Review slow-moving stock for {row["name"]}',
                       f'{row["stock"]} {row["unit"]} on hand now and sales on {row["selling_days"]} distinct days in the last 28 complete days.',
                       "Check past availability and merchandising before reordering", "/inventory")
    customers = customer_activity(business, start, end, today, zone)
    if customers and customers[0]["outstanding"] > 0:
        row = customers[0]
        recommendation("receivables", 1 if (row["age"] or 0) >= 30 else 2, f'Review balance for {row["name"]}',
                       f'{business.currency} {row["outstanding"]} across {row["open_invoices"]} open sales. Oldest open sale is {row["age"]} days old.',
                       "Review open invoices and follow up", "/customers")
    category_current = {row["name"]: row["amount"] for row in current["expense_categories"]}
    category_previous = {row["name"]: row["amount"] for row in previous["expense_categories"]}
    categories = [{ "name": name, "current": category_current.get(name, ZERO), "previous": category_previous.get(name, ZERO),
                   "delta": category_current.get(name, ZERO) - category_previous.get(name, ZERO)}
                  for name in sorted(category_current.keys() | category_previous.keys())]
    categories.sort(key=lambda row: (-abs(row["delta"]), row["name"]))
    comparable = (end - start) == (compare_end - compare_start) and end < today and compare_end < today
    previous_entries = Expense.objects.filter(business=business, category__business=business, voided=False,
                                               incurred_on__range=(compare_start, compare_end))
    selected_entries = Expense.objects.filter(business=business, category__business=business, voided=False,
                                               incurred_on__range=(start, end))
    baseline = {row["category_id"]: row["typical"] for row in previous_entries.order_by().values("category_id").annotate(
        typical=Avg("amount", output_field=WIDE), count=Count("id")).filter(count__gte=3)}
    unusual = []
    largest_entries = selected_entries.order_by().values("category_id", "category__name").annotate(peak=Max("amount"))
    for row in largest_entries:
        typical = baseline.get(row["category_id"])
        if typical and row["peak"] >= 3 * typical:
            unusual.append({"name": row["category__name"], "largest": money(row["peak"]), "baseline": money(typical)})
    unusual.sort(key=lambda row: (-row["largest"], row["name"]))
    for row in unusual[:3]:
        recommendation("outlier-" + row["name"], 2, f'Check an unusual {row["name"]} expense',
                       f'The largest selected entry was {business.currency} {row["largest"]}. The comparison average was {row["baseline"]}.',
                       "Check whether the expense was expected or recorded incorrectly", "/expenses")
    if comparable:
        for row in categories[:5]:
            if row["previous"] > 0 and row["delta"] >= row["previous"] / 2:
                recommendation("expense-" + row["name"], 2, f'Review increased {row["name"]} spending',
                               f'{business.currency} {row["current"]} versus {row["previous"]}, an increase of {row["delta"]}.',
                               "Review recorded expenses for recurring costs and one-off entries", "/expenses")
        for metric in metrics:
            if metric["key"] == "net_sales" and metric["percent"] is not None and abs(metric["percent"]) >= 20:
                recommendation("revenue-change", 2, "Investigate the net sales change",
                               f'Net sales moved {metric["percent"]:+}% across equal-length completed periods.',
                               "Review changes in volume, discounts, returns and product mix", "/reports")
    drivers = [
        {"label": "Gross sales movement", "delta": now["gross_sales"] - before["gross_sales"]},
        {"label": "Discount impact", "delta": before["discounts"] - now["discounts"]},
        {"label": "Returns impact", "delta": before["sales_returns"] - now["sales_returns"]},
        {"label": "Cost of goods impact", "delta": before["cogs"] - now["cogs"]},
        {"label": "Operating expense impact", "delta": before["operating_expenses"] - now["operating_expenses"]},
    ]
    ranked.sort(key=lambda row: (-row["revenue"], row["sku"]))
    return as_json(dict(start=current["start"], end=current["end"], comparison_start=previous["start"],
                        comparison_end=previous["end"], comparable=comparable, metrics=metrics, drivers=drivers,
                        series=current["series"], expenses=categories[:30], unusual=unusual[:20], products=ranked[:30],
                        low=low[:20], slow=slow[:20], active_days=active_days,
                        customers=customers[:20], outstanding=money(sum((row["outstanding"] for row in customers), ZERO)),
                        forecast=forecast(business, today),
                        recommendations=sorted(recommendations, key=lambda row: row["priority"])))
