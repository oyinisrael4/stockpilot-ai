import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest import skipUnless
from uuid import uuid4

from django.conf import settings
from django.test import override_settings
from rest_framework.test import APITestCase

from .assistant_tools import local_day
from .models import Business, Customer, Expense, ExpenseCategory, Membership, Product, ReturnLine, Sale, SaleLine, SalePayment, SaleReturn, User


class InsightsTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Insights fixture")
        self.owner = User.objects.create_user("insights", "insights@example.invalid")
        Membership.objects.create(business=self.business, user=self.owner, role="owner")
        self.client.force_authenticate(self.owner)
        self.base = f"/api/v1/businesses/{self.business.pk}/"
        self.today = local_day(self.business)
        self.start = self.today - timedelta(days=14)
        self.end = self.today - timedelta(days=8)
        self.product = Product.objects.create(business=self.business, name="Water", sku="WATER", stock=2,
                                              reorder_level=5, price=25, cost=10)
        Product.objects.filter(pk=self.product.id).update(created_at=self.product.created_at - timedelta(days=60))
        self.customer = Customer.objects.create(business=self.business, name="Harbor Café")
        self.category = ExpenseCategory.objects.create(business=self.business, name="Transport")

    def sale(self, day, *, count=4, customer=None, paid=None, discount=0):
        from datetime import datetime, time
        from zoneinfo import ZoneInfo

        posted = datetime.combine(day, time(12), ZoneInfo(self.business.timezone))
        revenue = 25 * count - discount
        sale = Sale.objects.create(business=self.business, actor=self.owner, status="completed", posted_at=posted,
                                   request_id=uuid4(), subtotal=25 * count, discount=discount, total=revenue,
                                   cogs=10 * count, paid=revenue if paid is None else paid, customer=customer)
        SaleLine.objects.create(business=self.business, sale=sale, product=self.product, name=self.product.name, sku=self.product.sku,
                                tracked=True, unit="unit", quantity=count, price=25, unit_cost=10, subtotal=25 * count,
                                discount=discount, tax=0, total=revenue, cogs=10 * count)
        return sale

    def expense(self, day, amount, **extra):
        return Expense.objects.create(business=self.business, actor=self.owner, category=self.category,
                                      incurred_on=day, amount=amount, method="cash", **extra)

    def fetch(self, **query):
        result = self.client.get(self.base + "insights/", {"start": self.start, "end": self.end, **query})
        self.assertEqual(result.status_code, 200, result.data)
        return result.data

    def test_financial_drivers_outliers_and_receivables_are_grounded(self):
        old_day = self.start - timedelta(days=2)
        self.sale(old_day, count=2)
        buyer_sale = self.sale(self.start, customer=self.customer, paid=25, discount=10)
        payment = SalePayment.objects.create(business=self.business, actor=self.owner, sale=buyer_sale,
                                              method="cash", amount=25, request_id=uuid4())
        SalePayment.objects.filter(pk=payment.pk).update(created_at=buyer_sale.posted_at + timedelta(days=1))
        for _ in range(3):
            self.expense(old_day, 5)
        self.expense(self.start, 20)
        self.expense(self.start, 500, voided=True)

        result = self.fetch()
        self.assertTrue(result["comparable"])
        totals = {row["key"]: row for row in result["metrics"]}
        self.assertEqual(totals["net_sales"]["current"], "90.00")
        self.assertEqual(totals["gross_profit"]["current"], "50.00")
        self.assertEqual(totals["operating_result"]["delta"], "15.00")
        self.assertEqual(sum(Decimal(row["delta"]) for row in result["drivers"]), Decimal("15.00"))
        self.assertEqual(result["products"][0]["previous_revenue"], "50.00")
        self.assertEqual(result["unusual"], [{"name": "Transport", "largest": "20.00", "baseline": "5.00"}])
        customer = result["customers"][0]
        self.assertEqual((customer["outstanding"], customer["payments"], customer["later_payments"], customer["age"]),
                         ("65.00", "25.00", 1, 14))
        self.assertEqual(result["outstanding"], "65.00")
        self.assertIsNone(result["low"][0]["suggested"])

    def test_returns_use_reversal_period_and_reversed_cost(self):
        sale = self.sale(self.start - timedelta(days=1), count=4)
        returned = SaleReturn.objects.create(business=self.business, sale=sale, actor=self.owner,
                                             request_id=uuid4(), total=25, cogs_reversed=10)
        SaleReturn.objects.filter(pk=returned.pk).update(created_at=sale.posted_at + timedelta(days=1))
        ReturnLine.objects.create(business=self.business, sale_return=returned, sale_line=sale.lines.get(),
                                  quantity=1, total=25, tax=0, cogs_reversed=10, restocked=True)
        result = self.fetch()
        self.assertEqual(result["products"][0]["revenue"], "-25.00")
        self.assertEqual(result["products"][0]["profit"], "-15.00")
        self.assertEqual(result["products"][0]["previous_revenue"], "100.00")
        self.assertEqual(next(row["delta"] for row in result["drivers"] if row["label"] == "Returns impact"), "-25.00")

    def test_forecast_and_reorder_require_history_and_are_labeled(self):
        result = self.fetch()
        self.assertFalse(result["forecast"]["available"])
        self.assertEqual(result["slow"], [])
        self.assertIsNone(result["low"][0]["suggested"])
        monday = self.today - timedelta(days=self.today.weekday())
        for index in range(1, 9):
            self.sale(monday - timedelta(weeks=index), count=4)
        for offset in range(1, 8):
            self.sale(self.today - timedelta(days=offset), count=4)
        slow = Product.objects.create(business=self.business, name="Slow", sku="SLOW", stock=25, price=25)
        Product.objects.filter(pk=slow.pk).update(created_at=slow.created_at - timedelta(days=60))
        result = self.fetch()
        self.assertTrue(result["forecast"]["available"])
        self.assertIn("observed", result["forecast"]["note"])
        self.assertEqual(result["forecast"]["estimate"], "100.00")
        self.assertGreater(Decimal(result["low"][0]["suggested"]), 3)
        self.assertEqual(result["slow"][0]["sku"], "SLOW")
        self.assertLessEqual(result["recommendations"][0]["priority"], result["recommendations"][-1]["priority"])

    def test_custom_comparison_empty_baseline_and_membership(self):
        other = Business.objects.create(name="Private")
        Product.objects.create(business=other, name="Confidential", sku="SECRET", stock=0)
        self.assertNotIn("Confidential", str(self.fetch()))
        self.assertEqual(self.client.get(f"/api/v1/businesses/{other.pk}/insights/",
                                         {"start": self.start, "end": self.end}).status_code, 404)
        result = self.fetch(compare_start=self.start - timedelta(days=30), compare_end=self.start - timedelta(days=20))
        self.assertFalse(result["comparable"])
        self.assertTrue(all(item["percent"] is None for item in result["metrics"]))
        self.assertEqual(self.client.get(self.base + "insights/", {"start": self.end, "end": self.start}).status_code, 400)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(self.base + "insights/").status_code, (401, 403))

    def send(self, thread, text):
        result = self.client.post(self.base + f"assistant/conversations/{thread}/messages/",
                                  {"request_id": str(uuid4()), "text": text}, format="json")
        self.assertEqual(result.status_code, 201, result.data)
        self.assertIsNone(result.data["proposal"])
        return result.data["answer"]

    @override_settings(ASSISTANT_PROVIDER="openai", ASSISTANT_MODEL="", ASSISTANT_API_KEY="")
    def test_demo_insights_followup_keeps_topic_and_comparison(self):
        self.sale(self.start)
        thread = self.client.post(self.base + "assistant/conversations/").data["id"]
        first = self.send(thread, f"Show product performance from {self.start} to {self.end}")
        self.assertEqual(first["card"]["rows"][0][2], {"money": "100.00"})
        detail = self.send(thread, "Explain the change")
        self.assertIn(str(self.start), detail["text"])
        self.assertEqual(detail["card"]["rows"][0], ["Gross sales movement", {"money": "100.00"}])

    @skipUnless(os.getenv("STOCKPILOT_RUN_LIVE_AI_TESTS") == "1", "Opt-in offline conversation test.")
    @override_settings(ASSISTANT_PROVIDER=settings.ASSISTANT_PROVIDER, ASSISTANT_MODEL=settings.ASSISTANT_MODEL,
                       ASSISTANT_API_KEY=settings.ASSISTANT_API_KEY)
    def test_live_model_insights_and_spoken_followup(self):
        self.sale(self.today - timedelta(days=1), discount=5)
        self.sale(self.today, count=1)
        previous_month = self.today.replace(day=1) - timedelta(days=1)
        self.sale(previous_month, count=2)
        thread = self.client.post(self.base + "assistant/conversations/").data["id"]
        answer = self.send(thread, "Which items contributed most to our gross profit this month?")
        self.assertEqual(answer["mode"], "provider", answer)
        self.assertEqual(answer.get("card", {}).get("title"), "Product performance", answer)
        expected = "15.00" if self.today.day == 1 else "70.00"
        self.assertEqual(answer["card"]["rows"][0][3], {"money": expected})
        example = os.getenv("STOCKPILOT_INSIGHTS_VOICE_WAV")
        if example:
            speech = self.client.post(self.base + "assistant/transcribe/", Path(example).read_bytes(), content_type="audio/wav")
            self.assertEqual(speech.status_code, 200, speech.data)
            followup = speech.data["text"]
            self.assertIn("last month", followup.casefold())
        else:
            followup = "What about last month?"
        answer = self.send(thread, followup)
        self.assertEqual(answer["mode"], "provider", answer)
        previous_profit = "85.00" if self.today.day == 1 else "30.00"
        self.assertEqual(answer["card"]["rows"][0][3], {"money": previous_profit})
        self.assertEqual(Sale.objects.filter(business=self.business).count(), 3)
