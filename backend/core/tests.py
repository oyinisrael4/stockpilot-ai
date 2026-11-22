from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from .models import AuditEvent, Business, Category, Membership, Product, Receipt, StockMovement, Supplier, User

PASSWORD = "Telescope#lumen47"
API = "/api/v1/"


@override_settings(SECURE_SSL_REDIRECT=False, CSRF_COOKIE_SECURE=False, SESSION_COOKIE_SECURE=False)
class AccountTests(APITestCase):
    def test_registration_csrf_session_and_logout(self):
        client = APIClient(enforce_csrf_checks=True)
        payload = {"username": "TestOwner", "email": "owner@example.invalid", "password": PASSWORD, "confirm_password": PASSWORD, "business_name": "Test workspace"}
        self.assertEqual(client.post(API + "auth/register/", payload).status_code, 403)
        session = client.get(API + "auth/session/")
        token = session.cookies["csrftoken"].value
        response = client.post(API + "auth/register/", payload, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Membership.objects.get().role, "owner")
        self.assertEqual(client.get(API + "auth/session/").data["user"]["username"], "testowner")
        self.assertEqual(client.post(API + "auth/logout/").status_code, 403)
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(API + "auth/logout/", HTTP_X_CSRFTOKEN=token).status_code, 204)
        self.assertEqual(client.get(API + "businesses/").status_code, 403)
        self.assertEqual(client.post(API + "auth/login/", {"username": "TESTOWNER", "password": PASSWORD}, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_reset_token_works_once(self):
        user = User.objects.create_user("tester", "tester@example.invalid", PASSWORD)
        self.assertEqual(self.client.post(API + "auth/reset/", {"email": user.email}).status_code, 204)
        link = mail.outbox[0].body.strip().splitlines()[-1]
        from urllib.parse import parse_qs, urlsplit

        params = {key: value[0] for key, value in parse_qs(urlsplit(link).fragment).items()}
        params["password"] = "Nebula+quartz74"
        self.assertEqual(self.client.post(API + "auth/reset/confirm/", params).status_code, 204)
        self.assertEqual(self.client.post(API + "auth/reset/confirm/", params).status_code, 400)
        user.refresh_from_db()
        self.assertTrue(user.check_password(params["password"]))


@override_settings(SECURE_SSL_REDIRECT=False)
class BusinessTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Fixture workspace")
        self.other = Business.objects.create(name="Another fixture")
        self.owner = User.objects.create_user("owner", "owner@example.invalid")
        self.viewer = User.objects.create_user("viewer", "viewer@example.invalid")
        Membership.objects.create(business=self.business, user=self.owner, role="owner")
        Membership.objects.create(business=self.business, user=self.viewer, role="viewer")
        Membership.objects.create(business=self.other, user=self.viewer, role="owner")
        self.client.force_authenticate(self.owner)
        self.path = API + f"businesses/{self.business.pk}/"
        self.product = Product.objects.create(business=self.business, name="Water", sku="WATER")
        self.foreign = Product.objects.create(business=self.other, name="Foreign item", sku="WATER")
        self.supplier = Supplier.objects.create(business=self.business, name="Fixture supplier")

    def test_tenant_isolation(self):
        self.assertEqual(self.client.get(API + f"businesses/{self.other.pk}/products/").status_code, 404)
        self.assertEqual(self.client.get(self.path + f"products/{self.foreign.pk}/").status_code, 404)
        category = Category.objects.create(business=self.other, name="Outside")
        response = self.client.patch(self.path + f"products/{self.product.pk}/", {"category": category.pk})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(self.path + "products/").data["count"], 1)

    def test_viewer_cannot_write_and_owner_can_grant_manager(self):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get(self.path + "products/").status_code, 200)
        self.assertEqual(self.client.post(self.path + "products/", {"name": "New", "sku": "X"}).status_code, 403)
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.path + "members/", {"username": self.viewer.username, "role": "manager"})
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.post(self.path + "products/", {"name": "New", "sku": "X"}).status_code, 201)
        self.assertEqual(self.client.patch(self.path + "settings/", {"name": "Other name"}).status_code, 403)

    def test_product_crud_and_validation(self):
        self.assertEqual(self.client.post(self.path + "products/", {"name": "Duplicate", "sku": "water"}).status_code, 400)
        self.assertEqual(self.client.post(self.path + "products/", {"name": "Invalid", "sku": "BAD", "price": "-0.01"}).status_code, 400)
        created = self.client.post(self.path + "products/", {"name": "Packaging", "sku": "pkg", "price": "12.50", "stock": "200"})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["stock"], "0.000")
        item = self.path + f"products/{created.data['id']}/"
        self.assertEqual(self.client.patch(item, {"price": "13.00"}).data["price"], "13.00")
        self.assertEqual(self.client.delete(item).status_code, 204)
        self.assertEqual(self.client.get(item).data["active"], False)
        self.assertEqual(self.client.get(self.path + "products/?search=PKG").data["count"], 0)
        self.assertEqual(self.client.get(self.path + "products/?state=archived&search=PKG").data["count"], 1)
        self.assertEqual(AuditEvent.objects.filter(action="product.updated").count(), 1)

    def test_opening_balance_once_and_cost_lock(self):
        payload = {"product": self.product.pk, "quantity": "100", "unit_cost": "150"}
        first = self.client.post(self.path + "movements/", payload)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data["balance"], "100.000")
        self.assertEqual(self.client.post(self.path + "movements/", payload).status_code, 400)
        self.assertEqual(self.client.patch(self.path + f"products/{self.product.pk}/", {"unit": "box"}).status_code, 400)
        self.assertEqual(StockMovement.objects.count(), 1)

    def receipt_payload(self):
        return {"supplier": self.supplier.pk, "request_id": str(uuid4()), "received_on": date(2020, 1, 1).isoformat(),
                "lines": [{"product": self.product.pk, "quantity": "25", "unit_cost": "200"}]}

    def test_purchase_weighted_cost_and_idempotency(self):
        self.client.post(self.path + "movements/", {"product": self.product.pk, "quantity": "100", "unit_cost": "150"})
        payload = self.receipt_payload()
        first = self.client.post(self.path + "receipts/", payload, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        retry = self.client.post(self.path + "receipts/", payload, format="json")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(first.data["id"], retry.data["id"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal("125.000"))
        self.assertEqual(self.product.cost, Decimal("160.0000"))
        self.assertEqual(Receipt.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 2)
        payload["lines"][0]["quantity"] = "30"
        self.assertEqual(self.client.post(self.path + "receipts/", payload, format="json").status_code, 400)

    def test_receiving_rolls_back_invalid_lines_and_rejects_foreign_product(self):
        payload = self.receipt_payload()
        payload["lines"].append({"product": self.foreign.pk, "quantity": "1", "unit_cost": "10"})
        self.assertEqual(self.client.post(self.path + "receipts/", payload, format="json").status_code, 400)
        self.assertFalse(Receipt.objects.exists())
        self.assertFalse(StockMovement.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def test_workspace_metrics_are_tenant_scoped(self):
        overview = self.client.get(self.path + "overview/")
        self.assertEqual(overview.data, {"products": 1, "tracked": 1, "low_stock": 1, "receipts": 0, "recent_movements": []})
