import re
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import F, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .assistant_intents import dates
from .finance_serializers import ReportInput
from .insights import insights
from .models import ExpenseCategory, Product, ReturnLine, Sale, SaleLine
from .reporting import WIDE, as_json, report, summed
from .sales import ZERO, exact_finance


def local_day(business):
    return timezone.localdate(timezone=ZoneInfo(business.timezone))


def tokens(value):
    words = re.findall(r"[^\W_]+", value.casefold())
    aliases = {"transportation": "transport", "bottles": "bottle", "bottled": "bottle",
               "boxes": "box", "pieces": "piece", "liters": "litre", "liter": "litre"}
    return {aliases.get(word, word[:-1] if len(word) > 3 and word.endswith("s") else word) for word in words}


def product_tokens(value):
    value = re.sub(r"\b(\d+)\s*(cl|ml)\b", r"\1\2", value.casefold())
    words = tokens(value) - {"of", "the", "that", "this"}
    if "water" in words:
        words = {word + "cl" if word.isascii() and word.isdecimal() and len(word) == 2 else word for word in words}
    return words


def match_records(queryset, value, *, catalog=False):
    value = value.strip()
    if not value or len(value) > 150:
        return []
    exact = Q(name__iexact=value)
    if catalog:
        exact |= Q(sku__iexact=value) | Q(barcode__iexact=value)
    matches = list(queryset.filter(exact).order_by("id")[:6])
    if matches:
        return matches
    tokenize = product_tokens if catalog else tokens
    search = tokenize(value)
    if not search:
        return []
    candidates = Q()
    for word in search:
        fragment = re.sub(r"(?:cl|ml)$", "", word) if re.fullmatch(r"\d+(?:cl|ml)", word) else word
        candidates |= Q(name__icontains=fragment)
    matches = []
    for record in queryset.filter(candidates).order_by("name", "id").iterator():
        if search.issubset(tokenize(record.name)) or (catalog and search.issubset(tokenize(record.sku))):
            matches.append(record)
            if len(matches) == 6:
                break
    return matches


def response(text, card=None, *, followup=None, choices=None):
    return {"text": text, **({"card": card} if card else {}), **({"followup": followup} if followup else {}),
            **({"choices": choices} if choices else {})}


def clarify(text, intent, field, choices=None):
    return response(text, followup={"intent": intent, "field": field}, choices=choices)


def matches_or_clarify(records, label, intent, field):
    if len(records) == 1:
        return records[0], None
    if not records:
        return None, clarify(f"Which {label} should I use? Enter its exact name" +
                             (" or SKU." if label == "product" else "."), intent, field)
    choices = [item.sku if label == "product" else item.name for item in records
               if label == "product" or sum(other.name.casefold() == item.name.casefold() for other in records) == 1]
    if not choices:
        return None, response(f"Multiple {label} records have that name. Use the manual form to select the exact record.")
    return None, clarify(f"Several {label} records match. Choose one below or enter its exact name.", intent, field, choices)


def select_range(intent, business):
    today = local_day(business)
    start, end = dates(intent.get("period"), today)
    params = {"start": start, "end": end}
    comparison = intent.get("comparison")
    if comparison == "previous":
        compare_end = start - timedelta(days=1)
        compare_start = compare_end - (end - start)
    elif comparison:
        compare_start, compare_end = dates(comparison, today)
    else:
        compare_start = compare_end = None
    if compare_start:
        params.update(compare_start=compare_start, compare_end=compare_end)
    serializer = ReportInput(data=params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def table(title, headers, rows, link=None):
    return {"kind": "table", "title": title, "headers": headers, "rows": rows, "link": link}


def product_stock(business, intent):
    products = Product.objects.filter(business=business, active=True)
    value = intent.get("entity", "")
    if value:
        item, question = matches_or_clarify(match_records(products, value, catalog=True), "product", intent, "entity")
        if question:
            return question
        stock = str(item.stock) if item.track_stock else "Untracked"
        return response("Here is the current catalog record.", table("Product availability", ["Product", "SKU", "On hand", "Unit"],
                        [[item.name, item.sku, stock, item.unit]], "/inventory"))
    low = products.filter(track_stock=True, stock__lte=F("reorder_level")).order_by("stock", "id")
    count = low.count()
    if not count:
        return response("No active tracked products are at or below their reorder level.")
    return response(f"{count} active tracked products are at or below their reorder level. Review supplier lead times before reordering.",
                    table("Low-stock watchlist", ["Product", "SKU", "On hand", "Reorder at", "Unit"],
                          [[p.name, p.sku, str(p.stock), str(p.reorder_level), p.unit] for p in low[:12]], "/inventory?low=1"))


@exact_finance
def receivables(business):
    balances = Sale.objects.filter(business=business, customer__business=business, status=Sale.Status.COMPLETED)
    balances = balances.order_by().values("customer_id", "customer__name").annotate(
        amount=Sum(F("total") - F("returned") - F("paid"), output_field=WIDE)).filter(amount__gt=0).order_by("-amount", "customer_id")
    rows = [[row["customer__name"], {"money": str(row["amount"])}] for row in balances[:12]]
    return response("These are the largest current unpaid customer balances." if rows else "There are no outstanding customer balances.",
                    table("Customer receivables", ["Customer", "Outstanding"], rows, "/customers") if rows else None)


def financial_card(result, action, category=None):
    current, comparison = result["current"], result["comparison"]
    metrics = {
        "profit": [("net_sales", "Net sales revenue"), ("cogs", "Cost of goods sold"),
                   ("gross_profit", "Gross profit"), ("operating_expenses", "Operating expenses"),
                   ("operating_result", "Net operating result")],
        "operating_loss": [("gross_profit", "Gross profit"), ("operating_expenses", "Operating expenses"),
                           ("operating_result", "Net operating result")],
        "sales": [("gross_sales", "Gross sales"), ("discounts", "Discounts"), ("sales_returns", "Returns excluding tax"),
                  ("net_sales", "Net sales revenue")],
        "returns": [("sales_returns", "Sales returns excluding tax"), ("refunds", "Refunds recorded")],
        "expenses": [("operating_expenses", "Operating expenses")],
    }
    rows = [{"label": label, "value": current["totals"][key], "comparison": comparison["totals"][key] if comparison else None}
            for key, label in metrics[action]]
    series = current["series"]
    if category:
        def total(data):
            return next((row["amount"] for row in data["expense_categories"] if row["name"] == category.name), "0.00")
        rows = [{"label": category.name, "value": total(current), "comparison": total(comparison) if comparison else None}]
        series = []
    return {"kind": "finance", "title": "Recorded business activity", "start": current["start"], "end": current["end"],
            "comparison": f'{comparison["start"]} to {comparison["end"]}' if comparison else None, "metrics": rows,
            "series": series, "link": "/reports"}


@exact_finance
def revenue_leaders(business, params):
    zone = ZoneInfo(business.timezone)
    start = datetime.combine(params["start"], time.min, zone)
    end = datetime.combine(params["end"] + timedelta(days=1), time.min, zone)
    sales = SaleLine.objects.filter(business=business, sale__posted_at__gte=start, sale__posted_at__lt=end)
    returns = ReturnLine.objects.filter(business=business, sale_return__created_at__gte=start, sale_return__created_at__lt=end)
    amounts = {row["product_id"]: row["amount"] for row in sales.order_by().values("product_id").annotate(
        amount=Sum(F("subtotal") - F("discount"), output_field=WIDE))}
    for row in returns.order_by().values("sale_line__product_id").annotate(amount=Sum(F("total") - F("tax"), output_field=WIDE)):
        key = row["sale_line__product_id"]
        amounts[key] = amounts.get(key, ZERO) - row["amount"]
    leaders = sorted((key for key in amounts if amounts[key] > 0), key=lambda key: (-amounts[key], key))[:5]
    names = Product.objects.filter(business=business, pk__in=leaders).in_bulk()
    return [[names[key].name, {"money": str(amounts[key])}] for key in leaders if key in names]


@exact_finance
def evidence(result):
    current, comparison = result["current"], result["comparison"]
    signals = []
    stock = result["inventory"]["low_stock"]
    if stock:
        item = stock[0]
        signals.append(f'{item["name"]} has {item["stock"]} {item["unit"]} on hand against a reorder level of '
                       f'{item["reorder_level"]}. Check open orders and supplier lead time before purchasing.')
    if current["totals"]["sale_count"] >= 3:
        slow = next((item for item in result["slow_products"] if Decimal(item["units"]) <= 0), None)
        if slow:
            signals.append(f'{slow["name"]} had {slow["units"]} net units in this period. Check how long it has been listed '
                           'and whether it was available before changing replenishment.')
        if result["top_products"]:
            top = result["top_products"][0]
            signals.append(f'{top["name"]} led by net units ({top["units"]} {top["unit"]}). Compare its margin and '
                           'availability before shifting the product mix.')
    if comparison:
        before = {row["name"]: Decimal(row["amount"]) for row in comparison["expense_categories"]}
        increases = sorted(((Decimal(row["amount"]) - before.get(row["name"], ZERO), row["name"])
                            for row in current["expense_categories"]), reverse=True)
        if increases and increases[0][0] > 0:
            amount, name = increases[0]
            signals.append(f"{name} increased by {amount:.2f} in the workspace currency. Review its expense entries "
                           "to distinguish higher recurring costs from one-off spending.")
        old, new = comparison["totals"], current["totals"]
        if old["gross_margin"] is not None and new["gross_margin"] is not None:
            change = Decimal(new["gross_margin"]) - Decimal(old["gross_margin"])
            if change:
                signals.append(f"Gross margin moved by {change:+.2f} percentage points. Compare cost, mix and discounts before attributing a cause.")
        if Decimal(new["net_sales"]) != Decimal(old["net_sales"]):
            signals.append(f'Net sales moved from {old["net_sales"]} to {new["net_sales"]} in the workspace currency. '
                           "Check the number of trading days, stock availability and discounts before drawing conclusions.")
    return signals


@exact_finance
def run_read_tool(business, intent):
    action = intent["action"]
    if action == "stock":
        return product_stock(business, intent)
    if action == "receivables":
        return receivables(business)
    if action == "valuation":
        products = Product.objects.filter(business=business, active=True, track_stock=True)
        value = summed(products, value=F("stock") * F("cost"))["value"]
        return response("Current inventory valuation uses on-hand quantity times weighted-average cost for active tracked products.",
                        table("Inventory valuation", ["Measure", "Value"], [["Current inventory", {"money": str(value)}]], "/inventory"))
    if action == "loss":
        return response("Which loss do you mean? I can calculate operating loss or recorded sales returns. Stock losses need a separate write-off record.",
                        choices=["Operating loss this month", "Sales returns this month"])
    if action == "unsupported":
        return response("Try a question about sales, profit, expenses, stock or customer balances. You can also prepare a sale, expense or purchase for review.")
    if action == "insights" and not intent.get("comparison"):
        intent = {**intent, "comparison": "previous"}
    try:
        params = select_range(intent, business)
    except (ValueError, OverflowError, ValidationError):
        return clarify("I couldn't resolve that period. Try “this week” or “2026-11-01 to 2026-11-08”.", intent, "period")
    category = None
    if action == "expenses" and intent.get("entity"):
        records = match_records(ExpenseCategory.objects.filter(business=business), intent["entity"])
        category, question = matches_or_clarify(records, "expense category", intent, "entity")
        if question:
            return question
    if action == "top" and intent.get("entity") == "revenue":
        rows = revenue_leaders(business, params)
        if not rows:
            return response("There are no products with positive recorded net revenue in that period.")
        return response(f'Net revenue after discounts and returns, excluding tax, from {params["start"]} through {params["end"]}.',
                        table("Products by net revenue", ["Product", "Net sales revenue"], rows, "/reports"))
    if action == "insights":
        return insight_answer(insights(business, **params), intent.get("entity", ""))
    result = report(business, **params)
    if action == "top":
        slow = intent.get("entity") == "slow"
        products = result["slow_products" if slow else "top_products"]
        current = result["current"]
        if not current["totals"]["sale_count"] and not any(Decimal(row["units"]) for row in products):
            return response("There is no recorded sales activity in that period to support a product ranking.")
        return response(f'Net units after returns from {current["start"]} through {current["end"]}.',
                        table("Slow-moving products" if slow else "Best-selling products", ["Product", "Net units", "Unit"],
                              [[row["name"], row["units"], row["unit"]] for row in products], "/reports"))
    if action == "operating_loss":
        amount = Decimal(result["current"]["totals"]["operating_result"])
        text = "Recorded activity shows an operating loss." if amount < 0 else "Recorded activity shows no operating loss for this period."
    elif action == "profit":
        text = "Gross profit is net sales less cost of goods sold. Net operating result also deducts recorded operating expenses."
    elif action == "expenses" and result["comparison"]:
        text = "Here is the recorded expense comparison. Category changes show where costs moved. Review the underlying entries to determine why."
    else:
        text = "Here are the figures from recorded transactions in the selected period."
    card = financial_card(result, action, category)
    if action == "expenses" and result["comparison"] and not category:
        card["observations"] = [item for item in evidence(result) if "expense entries" in item]
    return response(text, as_json(card))

def insight_answer(data, focus):
    label = f'{data["start"]} through {data["end"]}'
    if focus == "forecast":
        prediction = data["forecast"]
        card = table("Estimated net sales", ["Week", "Estimate", "Observed low", "Observed high"],
                     [[f'{prediction["start"]} to {prediction["end"]}',
                       *({"money": prediction[field]} for field in ("estimate", "low", "high"))]], "/insights") if prediction["available"] else None
        return response(prediction["note"], card)
    if focus == "drivers":
        return response(f'Operating-result drivers for {label}, versus {data["comparison_start"]} through '
                        f'{data["comparison_end"]}. These are accounting contributions. Investigate the underlying transactions for causes.'
                        + ("" if data["comparable"] else " The periods differ in length or include an incomplete day."),
                        table("What moved operating profit", ["Recorded component", "Impact"],
                              [[row["label"], {"money": row["delta"]}] for row in data["drivers"]], "/insights"))
    if focus == "products":
        return response(f'Product results for {label}, after recorded discounts and returns, excluding tax.',
                        table("Product performance", ["Product", "Net units", "Net sales", "Gross profit"],
                              [[row["name"], row["units"], {"money": row["revenue"]}, {"money": row["profit"]}]
                               for row in data["products"][:8]], "/insights") if data["products"] else None)
    if focus == "expenses":
        flags = " ".join(f'{row["name"]} had a largest entry of {row["largest"]} versus a comparison average of '
                         f'{row["baseline"]} in workspace currency.' for row in data["unusual"][:3])
        return response(f'Expense category changes for {label}. Review the entries for one-off charges and recurring costs.'
                        + ("" if data["comparable"] else " The periods differ in length or include an incomplete day."),
                        table("Expense changes", ["Category", "Selected", "Comparison", "Change"],
                              [[row["name"], *({"money": row[key]} for key in ("current", "previous", "delta"))]
                               for row in data["expenses"][:8]], "/insights") if data["expenses"] else None)
    if focus == "payments":
        return response("Outstanding balances and invoice age are current. Collections cover " + label + ". Invoice age measures time since posting.",
                        table("Customer payment activity", ["Customer", "Outstanding", "Oldest open (days)", "Payments collected", "Later payments"],
                              [[row["name"], {"money": row["outstanding"]}, str(row["age"]) if row["age"] is not None else "—",
                                {"money": row["payments"]}, str(row["later_payments"])] for row in data["customers"][:8]], "/insights")
                        if data["customers"] else None)
    if focus in ("restocking", "slow"):
        restock = focus == "restocking"
        rows = data["low" if restock else "slow"]
        return response(("Current stock and sales from the last 28 complete days. Reorder estimates target 14 days of demand or the configured reorder level, whichever is higher. Check supplier lead time and open orders."
                         if restock else "Slow-moving candidates had sales on at most one day in the last 28 complete days. Check past availability before changing purchasing.")
                        if rows else "The current stock and recorded sales provide no supported candidates.",
                        table("Reorder review" if restock else "Slow-moving candidates",
                              ["Product", "On hand", "Selling days"] + (["Estimated reorder"] if restock else []),
                              [[row["name"], f'{row["stock"]} {row["unit"]}', str(row["selling_days"])]
                               + ([row["suggested"] or "Insufficient history"] if restock else []) for row in rows[:8]], "/insights") if rows else None)
    items = [" ".join(filter(None, (row["title"] + ".", row["evidence"], row["estimate"], row["action"] + ".")))
             for row in data["recommendations"][:6]]
    return response("Here are the highest priority items supported by the workspace records." if items else
                    "The selected records do not support a priority recommendation yet. Open Insights to review the exact figures and data coverage.",
                    {"kind": "insights", "items": items, "link": "/insights"} if items else None,
                    choices=["Explain the change", "Review restocking recommendations", "Forecast net sales"])
