from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as utc
from decimal import Decimal
from threading import Barrier
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.db import close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from .models import AuditEvent, Business, Customer, Membership, Product, Sale, SalePayment, SaleReturn, StockMovement, User
from .sales import save_sale


class FinanceTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Water fixture")
        self.user = User.objects.create_user("operator", "operator@example.invalid")
        Membership.objects.create(business=self.business, user=self.user, role="owner")
        self.product = Product.objects.create(business=self.business, name="Bottled water", sku="WATER", price="250", cost="150", stock="100")
        self.customer = Customer.objects.create(business=self.business, name="Fixture customer")
        self.client.force_authenticate(self.user)
        self.path = f"/api/v1/businesses/{self.business.pk}/"
        self.today = timezone.localdate(timezone=ZoneInfo(self.business.timezone))

    def post(self, resource, payload):
        return self.client.post(self.path + resource, payload, format="json")

    def payload(self, total="2250", *, customer=None, payments=None):
        return {
            "request_id": str(uuid4()), "customer": customer,
            "lines": [{"product": self.product.pk, "quantity": "10"}],
            "discount": {"kind": "percent", "value": "10"},
            "expected_total": total,
            "payments": [{"method": "cash", "amount": total}] if payments is None else payments,
        }

    def checkout(self, payload=None):
        response = self.post("sales/checkout/", payload or self.payload())
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def report(self, start=None, end=None, **params):
        response = self.client.get(self.path + "reports/", {"start": start or self.today, "end": end or self.today, **params})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_checkout_stock_and_snapshot(self):
        sale = self.checkout()
        self.assertEqual((sale["status"], sale["total"], sale["balance"]), ("completed", "2250.00", "0.00"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("90"))
        self.assertEqual(StockMovement.objects.get().quantity, Decimal("-10"))
        Product.objects.filter(pk=self.product.pk).update(cost="500")
        self.assertEqual(self.report()["current"]["totals"]["cogs"], "1500.00")

    def test_fixed_line_percentage_invoice_and_tax(self):
        Product.objects.filter(pk=self.product.pk).update(taxable=True)
        Business.objects.filter(pk=self.business.pk).update(tax_rate="7.50")
        payload = self.payload("2322")
        payload["lines"][0]["discount"] = {"kind": "fixed", "value": "100"}
        sale = self.checkout(payload)
        self.assertEqual((sale["subtotal"], sale["discount"], sale["tax"], sale["total"]),
                         ("2500.00", "340.00", "162.00", "2322.00"))
        self.assertEqual(sale["lines"][0]["total"], "2322.00")

    def test_percentage_line_fixed_invoice_and_exact_allocation(self):
        second = Product.objects.create(business=self.business, name="Other water", sku="OTHER", price="1.00", track_stock=False)
        payload = self.payload("1.99")
        Product.objects.filter(pk=self.product.pk).update(price="2.00")
        payload["lines"] = [
            {"product": self.product.pk, "quantity": "1", "discount": {"kind": "percent", "value": "50"}},
            {"product": second.pk, "quantity": "1"},
        ]
        payload["discount"] = {"kind": "fixed", "value": "0.01"}
        sale = self.checkout(payload)
        self.assertEqual([line["total"] for line in sale["lines"]], ["0.99", "1.00"])
        self.assertEqual(sale["discount"], "1.01")

    def test_oversell_stale_quote_and_walk_in_credit_leave_no_effects(self):
        payload = self.payload()
        payload["lines"][0]["quantity"] = "101"
        self.assertEqual(self.post("sales/checkout/", payload).status_code, 400)
        self.assertEqual(self.post("sales/checkout/", self.payload("2000")).status_code, 400)
        self.assertEqual(self.post("sales/checkout/", self.payload(payments=[])).status_code, 400)
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(StockMovement.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("100"))

    def test_split_payment_duplicate_sale_and_outstanding_collection(self):
        payload = self.payload(customer=self.customer.pk, payments=[
            {"method": "cash", "amount": "1000"}, {"method": "transfer", "amount": "500"},
        ])
        sale = self.checkout(payload)
        self.assertEqual(self.post("sales/checkout/", payload).status_code, 200)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(SalePayment.objects.count(), 2)
        self.assertEqual(self.client.get(self.path + f"customers/{self.customer.pk}/").data["balance"], "750.00")
        self.assertEqual(self.report()["outstanding"], "750.00")
        payment = {"request_id": str(uuid4()), "amount": "750", "method": "card"}
        route = f"sales/{sale['id']}/record-payment/"
        self.assertEqual(self.post(route, payment).data["balance"], "0.00")
        self.assertEqual(self.post(route, payment).status_code, 200)
        self.assertEqual(SalePayment.objects.count(), 3)
        self.assertEqual(self.post(route, {**payment, "amount": "751"}).status_code, 400)

    def test_partial_then_full_return_and_retry(self):
        sale = self.checkout()
        route = f"sales/{sale['id']}/"
        line = sale["lines"][0]["id"]
        partial = {"request_id": str(uuid4()), "reason": "Damaged", "expected_refund": "450", "refund_method": "cash",
                   "lines": [{"sale_line": line, "quantity": "2", "restocked": False}]}
        quote = self.post(route + "return-quote/", partial)
        self.assertEqual(quote.data["refund"], "450.00")
        self.assertEqual(SaleReturn.objects.count(), 0)
        self.assertEqual(self.post(route + "return/", {**partial, "expected_refund": "449"}).status_code, 400)
        first = self.post(route + "return/", partial)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(self.post(route + "return/", partial).status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("90"))
        remaining = {**partial, "request_id": str(uuid4()), "reason": "Unopened", "expected_refund": "1800",
                     "lines": [{"sale_line": line, "quantity": "8", "restocked": True}]}
        last = self.post(route + "return/", remaining)
        self.assertEqual(last.status_code, 201, last.data)
        self.assertEqual(self.post(route + "return/", {**remaining, "request_id": str(uuid4())}).status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("98"))
        totals = self.report()["current"]["totals"]
        self.assertEqual((totals["sales_returns"], totals["net_sales"], totals["cogs"], totals["gross_profit"]),
                         ("2250.00", "0.00", "300.00", "-300.00"))

    def test_credit_return_reduces_receivable_before_refund_and_void_restocks(self):
        sale = self.checkout(self.payload(customer=self.customer.pk, payments=[{"method": "cash", "amount": "1000"}]))
        route = f"sales/{sale['id']}/"
        payload = {"request_id": str(uuid4()), "reason": "Wrong quantity", "expected_refund": "0",
                   "lines": [{"sale_line": sale["lines"][0]["id"], "quantity": "1", "restocked": True}]}
        self.assertEqual(self.post(route + "return/", payload).status_code, 201)
        self.assertEqual(self.report()["outstanding"], "1025.00")
        void = {"request_id": str(uuid4()), "reason": "Cancelled", "expected_refund": "1000", "refund_method": "cash"}
        self.assertEqual(self.post(route + "void/", void).status_code, 201)
        self.assertEqual(self.post(route + "void/", void).status_code, 200)
        self.assertEqual(self.client.get(self.path + route).data["status"], "voided")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("100"))
        self.assertEqual(self.report()["outstanding"], "0.00")

    def test_draft_can_resume_without_stock_or_financial_side_effects(self):
        payload = self.payload()
        draft = self.post("sales/draft/", payload)
        self.assertEqual(draft.status_code, 200, draft.data)
        self.assertEqual(draft.data["status"], "draft")
        self.assertEqual(self.report()["current"]["totals"]["sale_count"], 0)
        self.assertFalse(StockMovement.objects.exists())
        sale = self.checkout(payload)
        self.assertEqual(draft.data["id"], sale["id"])

    def test_expense_profit_report_comparison_and_audit(self):
        self.checkout()
        category = self.post("expense-categories/", {"name": "Transport"})
        self.assertEqual(category.status_code, 201, category.data)
        expense = self.post("expenses/", {"category": category.data["id"], "amount": "300", "incurred_on": self.today,
                                         "description": "Transport", "method": "cash"})
        self.assertEqual(expense.status_code, 201, expense.data)
        yesterday = self.today - timedelta(days=1)
        report = self.report(compare_start=yesterday, compare_end=yesterday)
        totals = report["current"]["totals"]
        self.assertEqual([totals[key] for key in ("gross_sales", "discounts", "net_sales", "cogs", "gross_profit", "gross_margin", "operating_expenses", "operating_result")],
                         ["2500.00", "250.00", "2250.00", "1500.00", "750.00", "33.33", "300.00", "450.00"])
        self.assertEqual(report["comparison"]["totals"]["net_sales"], "0.00")
        self.assertEqual(report["inventory"]["valuation"], "13500.00")
        self.assertEqual(report["current"]["series"][0]["net_sales"], "2250.00")
        export = self.client.get(self.path + "reports/csv/", {"start": self.today, "end": self.today})
        self.assertContains(export, "operating result,450.00")
        path = self.path + f"expenses/{expense.data['id']}/"
        self.assertEqual(self.client.patch(path, {"amount": "320"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(path, {"amount": "320", "reason": "Invoice corrected"}, format="json").status_code, 200)
        event = AuditEvent.objects.get(action="expense.corrected")
        self.assertEqual((event.details["before"]["amount"], event.details["after"]["amount"]), ("300.00", "320.00"))
        self.assertEqual(self.report()["current"]["totals"]["operating_result"], "430.00")
        self.assertEqual(self.post(f"expenses/{expense.data['id']}/void/", {"reason": "Duplicate receipt"}).status_code, 200)
        self.assertEqual(self.report()["current"]["totals"]["operating_result"], "750.00")

    def test_business_timezone_inclusive_dates(self):
        sale = self.checkout()
        Sale.objects.filter(pk=sale["id"]).update(posted_at=datetime(2026, 10, 31, 23, 30, tzinfo=utc.utc))
        self.assertEqual(self.report("2026-10-31", "2026-10-31")["current"]["totals"]["sale_count"], 0)
        report = self.report("2026-11-01", "2026-11-01", group="week")
        self.assertEqual(report["current"]["totals"]["sale_count"], 1)
        self.assertEqual(report["current"]["series"][0]["date"], "2026-10-26")

    def test_tenant_and_role_isolation(self):
        sale = self.checkout()
        outsider = User.objects.create_user("outside", "outside@example.invalid")
        outside = Business.objects.create(name="Other tenant")
        Membership.objects.create(business=outside, user=outsider, role="owner")
        outsider_customer = Customer.objects.create(business=outside, name="Other customer")
        payload = self.payload(customer=outsider_customer.pk)
        self.assertEqual(self.post("sales/checkout/", payload).status_code, 400)
        self.client.force_authenticate(outsider)
        self.assertEqual(self.client.get(self.path + f"sales/{sale['id']}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/businesses/{outside.pk}/sales/{sale['id']}/").status_code, 404)
        Membership.objects.create(business=self.business, user=outsider, role="cashier")
        self.assertEqual(self.post(f"sales/{sale['id']}/void/", {}).status_code, 403)
        self.assertEqual(self.post("expenses/", {}).status_code, 403)


class ConcurrentCheckoutTests(TransactionTestCase):
    def test_only_one_concurrent_checkout_can_consume_stock(self):
        business = Business.objects.create(name="Concurrency fixture")
        user = User.objects.create_user("concurrent", "concurrent@example.invalid")
        product = Product.objects.create(business=business, name="Water", sku="WATER", price="1", cost="0.50", stock="100")
        gate = Barrier(2)
        discount = {"kind": "fixed", "value": Decimal("0.00")}

        def attempt():
            close_old_connections()
            try:
                gate.wait(timeout=5)
                save_sale(business, user, {
                    "request_id": uuid4(), "customer": None, "notes": "", "discount": discount,
                    "lines": [{"product": product.pk, "quantity": Decimal("70"), "discount": discount}],
                    "payments": [{"method": "cash", "amount": Decimal("70.00")}], "expected_total": Decimal("70.00"),
                })
                return True
            except ValidationError:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(results, [True, False])
        product.refresh_from_db()
        self.assertEqual(product.stock, Decimal("30"))
        self.assertEqual(Sale.objects.count(), 1)
