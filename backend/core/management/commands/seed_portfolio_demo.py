"""Populate a dedicated development database with a fictional distributor."""
import os
from datetime import datetime, time, timedelta
from decimal import Decimal
from getpass import getpass
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from core.models import Business, Category, Customer, ExpenseCategory, Membership, Product, Supplier, User
from core.sales import calculate, record_payment, reverse_sale, save_sale
from core.services import open_stock, receive_stock, record_expense


class Command(BaseCommand):
    help = "Create the fictional Juniper Market Supply workspace in an empty stockpilot_demo database."

    def handle(self, *args, **options):
        if not settings.DEBUG or connection.settings_dict["NAME"] != "stockpilot_demo":
            raise CommandError("Demo seeding requires DJANGO_DEBUG=1 and the dedicated stockpilot_demo database.")
        if Business.objects.exists() or User.objects.exists():
            raise CommandError("Demo seeding requires an empty database. Existing data was left untouched.")
        password = os.environ.get("STOCKPILOT_DEMO_PASSWORD") or getpass("Choose a password for demo-owner: ")
        profile = User(username="demo-owner", email="owner@juniper.example.invalid", first_name="Avery")
        try:
            validate_password(password, profile)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from None
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("LOCK TABLE core_business, core_user IN SHARE ROW EXCLUSIVE MODE")
            if Business.objects.exists() or User.objects.exists():
                raise CommandError("Demo database is no longer empty.")
            self.seed(profile, password)
        self.stdout.write(self.style.SUCCESS("Created Juniper Market Supply · Demo. Username: demo-owner"))

    def seed(self, owner, password):
        zone = ZoneInfo("Africa/Lagos")
        today = timezone.localdate(timezone=zone)

        def at(days_ago, hour=10):
            day = today - timedelta(days=days_ago)
            instant = datetime.combine(day, time(hour), tzinfo=zone)
            return patch("django.utils.timezone.now", return_value=min(instant, real_now))

        real_now = timezone.now()
        D = Decimal
        with at(76):
            owner.set_password(password)
            owner.save()
            business = Business.objects.create(name="Juniper Market Supply · Demo", timezone="Africa/Lagos", currency="NGN")
            Membership.objects.create(business=business, user=owner, role=Membership.Role.OWNER)
            drinks = Category.objects.create(business=business, name="Beverages")
            pantry = Category.objects.create(business=business, name="Pantry")
            supplier = Supplier.objects.create(business=business, name="Fern Coast Wholesale")
            customers = [Customer.objects.create(business=business, name=name)
                         for name in ("Maple Street Café", "Palm Court Grocers", "Riverside Deli")]
            categories = {name: ExpenseCategory.objects.create(business=business, name=name)
                          for name in ("Transport", "Utilities", "Packaging", "Store rent")}
            products = []
            for category, name, sku, barcode, price, cost, quantity, reorder in (
                (drinks, "Spring Water 75 cl", "WATER-75", "200000000001", "350", "200", "1600", "120"),
                (drinks, "Sparkling Water 50 cl", "SPARK-50", "200000000002", "650", "390", "78", "32"),
                (drinks, "Hibiscus Cooler 33 cl", "HIB-33", "200000000003", "750", "420", "650", "60"),
                (pantry, "Plantain Crisps 75 g", "CRISP-75", "200000000004", "1200", "740", "800", "72"),
                (pantry, "Roasted Cashews 100 g", "CASHEW-100", "200000000005", "1850", "1150", "420", "50"),
                (pantry, "Ginger Tea 20 bags", "TEA-20", "200000000006", "2400", "1560", "65", "10"),
            ):
                product = Product.objects.create(business=business, category=category, name=name, sku=sku,
                                                 barcode=barcode, price=D(price), reorder_level=D(reorder))
                art = {"WATER-75": "spring-water", "SPARK-50": "sparkling-water", "HIB-33": "hibiscus",
                       "CRISP-75": "plantain", "TEA-20": "ginger-tea", "CASHEW-100": "cashews"}
                product.image_url = "http://127.0.0.1:5196/portfolio/" + art[sku] + ".webp"
                product.save(update_fields=["image_url"])
                open_stock(business, owner, product.id, D(quantity), D(cost))
                products.append(product)

        for offset in range(70, -1, -1):
            day = today - timedelta(days=offset)
            if offset in (44, 17):
                with at(offset, 8):
                    receive_stock(business, owner, uuid4(), supplier, day, f"JMS-{offset:03}", [
                        {"product": products[0].id, "quantity": D(160), "unit_cost": D(210)},
                        {"product": products[2].id, "quantity": D(120), "unit_cost": D(435)},
                    ])
            if day.weekday() == 6:
                continue
            with at(offset):
                product = products[[1, 2, 3, 4][offset % 4]]
                ticket = {
                    "request_id": uuid4(), "notes": "Fictional demonstration transaction",
                    "customer": customers[offset % 3].id if offset % 4 == 0 else None,
                    "discount": {"kind": "percent", "value": D(5 if offset % 9 == 0 else 0)},
                    "lines": [
                        {"product": products[0].id, "quantity": D(11 + offset % 9), "discount": {"kind": "fixed", "value": D(0)}},
                        {"product": product.id, "quantity": D(4 + offset % 4), "discount": {"kind": "fixed", "value": D(0)}},
                    ],
                }
                _, totals = calculate(business, ticket)
                total = totals["total"]
                paid = (total / 2).quantize(D(".01")) if ticket["customer"] else total
                sale, _ = save_sale(business, owner, {**ticket, "expected_total": total,
                                                    "payments": [{"method": "transfer" if offset % 3 == 0 else "cash", "amount": paid}]})
                if ticket["customer"] and offset > 12:
                    with at(offset - 3, 13):
                        record_payment(business, owner, sale.pk, {"request_id": uuid4(), "method": "transfer", "amount": sale.balance})
                if offset in (8, 33):
                    with at(offset - 1):
                        payload = {"request_id": uuid4(), "reason": "Unopened item returned", "refund_method": "cash",
                                   "lines": [{"sale_line": sale.lines.first().pk, "quantity": D(1), "restocked": True}]}
                        quote = reverse_sale(business, owner, sale.pk, payload, preview=True)
                        reverse_sale(business, owner, sale.pk, {**payload, "expected_refund": D(quote["refund"])})
                if day.weekday() in (0, 2, 4):
                    for name, amount in (("Transport", 3200 + offset % 5 * 250), ("Packaging", 850 + offset % 4 * 150)):
                        record_expense(business, owner, {"category": categories[name], "incurred_on": day, "amount": D(amount),
                                                         "description": f"Fictional {name.lower()} cost", "method": "transfer"})
                if day.day in (1, 15) or offset == 1:
                    category = "Store rent" if day.day == 1 else "Utilities"
                    record_expense(business, owner, {"category": categories[category], "incurred_on": day,
                                                     "amount": D(62000 if category == "Store rent" else 8800),
                                                     "description": f"Fictional {category.lower()} invoice", "method": "transfer"})
