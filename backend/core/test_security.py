from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient, APITestCase

from .inference import InferenceBusy, inference_slot
from .models import Business, Membership, Product, Receipt, Supplier, User
from .services import receive_stock
from decimal import Decimal


class SecurityTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user("security-owner", "security@example.invalid", "Fixture!Wavelength459")
        self.business = Business.objects.create(name="Security fixture")
        Membership.objects.create(business=self.business, user=self.owner, role="owner")
        self.other = Business.objects.create(name="Private fixture")
        self.client.force_authenticate(self.owner)
        self.base = f"/api/v1/businesses/{self.business.pk}/"

    def tearDown(self):
        cache.clear()

    def test_every_tenant_collection_rejects_foreign_workspace(self):
        resources = ["settings", "members", "products", "categories", "suppliers", "receipts", "movements",
                     "overview", "customers", "sales", "returns", "expense-categories", "expenses", "reports",
                     "reports/csv", "insights", "assistant/status", "assistant/conversations", "assistant/proposals"]
        for resource in resources:
            result = self.client.get(f"/api/v1/businesses/{self.other.pk}/{resource}/")
            self.assertEqual(result.status_code, 404, resource)

    def test_role_matrix_for_manual_writes_and_financial_actions(self):
        user = User.objects.create_user("roles", "roles@example.invalid")
        membership = Membership.objects.create(business=self.business, user=user, role="viewer")
        self.client.force_authenticate(user)
        for role in ("viewer", "analyst", "cashier", "manager"):
            membership.role = role
            membership.save()
            for resource in ("products", "categories", "suppliers", "receipts", "expenses", "expense-categories"):
                result = self.client.post(self.base + resource + "/", {}, format="json")
                self.assertEqual(result.status_code, 400 if role == "manager" else 403, (role, resource))
            self.assertEqual(self.client.post(self.base + "sales/checkout/", {}, format="json").status_code,
                             400 if role in ("cashier", "manager") else 403)
            self.assertEqual(self.client.patch(self.base + "settings/", {}, format="json").status_code, 403)

    def test_csrf_body_limit_and_private_cache_headers(self):
        client = APIClient(enforce_csrf_checks=True)
        result = client.get("/api/v1/auth/session/")
        self.assertIn("no-store", result["Cache-Control"])
        self.assertEqual(client.get("/api/v1/auth/session/", HTTP_ACCEPT="a" * 4097).status_code, 431)
        self.assertEqual(self.client.generic("POST", "/api/v1/auth/login/", b"{}", content_type="application/json; charset=zlib_codec").status_code, 415)
        self.assertEqual(self.client.get(self.base + "products/", {"search": "x" * 201}).status_code, 400)
        self.assertEqual(self.client.get(self.base + "products/?search=" + "x" * 4100).status_code, 414)
        self.assertEqual(client.post("/api/v1/auth/login/", {"username": "security-owner", "password": "Fixture!Wavelength459", "confirm_password": "Fixture!Wavelength459"}).status_code, 403)
        result = self.client.generic("POST", self.base + "assistant/transcribe/", b"x" * (2 * 1024 * 1024 + 1),
                                     content_type="audio/wav")
        self.assertEqual(result.status_code, 413)
        self.assertEqual(self.client.get(self.base + "products/", HTTP_ORIGIN="https://untrusted.example").get("Access-Control-Allow-Origin"), None)

    @override_settings(ALLOW_REGISTRATION=False)
    def test_registration_can_be_closed_without_removing_login(self):
        self.assertEqual(self.client.post("/api/v1/auth/register/", {}, format="json").status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post("/api/v1/auth/login/", {"username": self.owner.username,
                           "password": "Fixture!Wavelength459", "confirm_password": "Fixture!Wavelength459"}, format="json").status_code, 200)

    @patch("core.views.send_mail", side_effect=OSError("private transport detail"))
    def test_reset_delivery_failure_has_generic_response_and_safe_log(self, send):
        with self.assertLogs("core.views", "WARNING") as capture:
            result = self.client.post("/api/v1/auth/reset/", {"email": self.owner.email}, format="json")
        self.assertEqual(result.status_code, 204)
        self.assertNotIn("private transport detail", str(capture.output))
        import logging
        from .logging import SafeErrorFilter
        error = logging.LogRecord("django.request", logging.ERROR, "", 1, "private database content", (),
                                  (ValueError, ValueError("private value"), None))
        SafeErrorFilter().filter(error)
        self.assertNotIn("private", error.getMessage())
        self.assertIsNone(error.exc_info)
        self.assertEqual(self.client.post("/api/v1/auth/reset/", {"email": "absent@example.invalid"}, format="json").status_code, 204)

    def test_authentication_throttle_is_per_ip_even_after_login(self):
        self.client.force_authenticate(None)
        for _ in range(12):
            result = self.client.post("/api/v1/auth/login/", {"username": "nobody", "password": "incorrect", "confirm_password": "incorrect"}, format="json", HTTP_X_FORWARDED_FOR=f"198.51.100.{_}")
            self.assertEqual(result.status_code, 400)
        self.assertEqual(self.client.post("/api/v1/auth/login/", {}, format="json").status_code, 429)

    def test_catalog_query_count_does_not_grow_per_product(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        Product.objects.bulk_create([Product(business=self.business, name=f"Item {i}", sku=f"Q-{i}") for i in range(10)])
        with CaptureQueriesContext(connection) as small:
            self.assertEqual(self.client.get(self.base + "products/").status_code, 200)
        Product.objects.bulk_create([Product(business=self.business, name=f"Item {i}", sku=f"Q-{i}") for i in range(10, 110)])
        with CaptureQueriesContext(connection) as large:
            self.assertEqual(self.client.get(self.base + "products/").status_code, 200)
        self.assertLessEqual(len(large), len(small) + 1)

    def test_shared_inference_budget_releases_on_failure(self):
        with inference_slot():
            with self.assertRaises(InferenceBusy):
                with inference_slot():
                    self.fail("Concurrent inference was admitted.")
        try:
            with inference_slot():
                raise RuntimeError("fixture")
        except RuntimeError:
            pass
        with inference_slot():
            pass

    @override_settings(ASSISTANT_PROVIDER="ollama", ASSISTANT_MODEL="fixture:4b")
    @patch("core.assistant_intents.build_opener")
    def test_busy_model_returns_clear_error_without_contacting_inference(self, opener):
        thread = self.client.post(self.base + "assistant/conversations/").data["id"]
        with inference_slot():
            result = self.client.post(self.base + f"assistant/conversations/{thread}/messages/",
                                      {"text": "How much profit today?", "request_id": str(uuid4())}, format="json")
        self.assertEqual(result.status_code, 201)
        self.assertIn("busy", result.data["answer"]["text"])
        opener.return_value.open.assert_not_called()


class ConcurrentReceiptTests(TransactionTestCase):
    def test_same_receipt_key_posts_once_and_preserves_other_workspace(self):
        business = Business.objects.create(name="Concurrent receipts")
        other = Business.objects.create(name="Independent workspace")
        user = User.objects.create_user("receipt-owner", "receipts@example.invalid")
        supplier = Supplier.objects.create(business=business, name="Supplier")
        product = Product.objects.create(business=business, name="Water", sku="W")
        foreign = Product.objects.create(business=other, name="Water", sku="W", stock=7)
        gate, request_id = Barrier(2), uuid4()

        def receive():
            close_old_connections()
            try:
                gate.wait(timeout=10)
                return receive_stock(business, user, request_id, supplier, business.created_at.date(), "", [
                    {"product": product.pk, "quantity": Decimal(10), "unit_cost": Decimal(2)}])[1]
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: receive(), range(2)))
        self.assertCountEqual(results, [True, False])
        product.refresh_from_db()
        foreign.refresh_from_db()
        self.assertEqual(product.stock, 10)
        self.assertEqual(foreign.stock, 7)
        self.assertEqual(Receipt.objects.filter(business=business).count(), 1)
