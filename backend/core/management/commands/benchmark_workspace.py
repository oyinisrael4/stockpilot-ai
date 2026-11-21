"""Create and measure a fictional scale fixture only in stockpilot_perf."""
import json
from datetime import timedelta
from decimal import Decimal
from statistics import median
from time import perf_counter
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Business, Membership, Product, Sale, SaleLine, User


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        if connection.settings_dict["NAME"] != "stockpilot_perf":
            raise CommandError("Use only the isolated stockpilot_perf database.")
        business = Business.objects.first()
        if business is None:
            with transaction.atomic():
                business = Business.objects.create(name="Fictional scale benchmark")
                user = User.objects.create_user("perf-owner", "perf@example.invalid")
                Membership.objects.create(business=business, user=user, role="owner")
                products = Product.objects.bulk_create([
                    Product(business=business, name=f"Fixture item {index:05}", sku=f"PERF-{index:05}",
                            price=25, cost=10, stock=100, reorder_level=10) for index in range(10000)])
                sales = Sale.objects.bulk_create([
                    Sale(business=business, actor=user, status="completed", posted_at=timezone.now()-timedelta(days=index % 90),
                         request_id=uuid4(), subtotal=100, total=100, cogs=40, paid=100) for index in range(3000)])
                SaleLine.objects.bulk_create([
                    SaleLine(business=business, sale=sale, product=products[index % 300],
                             name=products[index % 300].name, sku=products[index % 300].sku, unit="unit", tracked=True,
                             quantity=4, price=25, unit_cost=10, subtotal=100, discount=0, tax=0, total=100, cogs=40)
                    for index, sale in enumerate(sales)])
        user = Membership.objects.get(business=business, role="owner").user
        client = APIClient(HTTP_HOST="127.0.0.1")
        client.force_authenticate(user)
        today = timezone.localdate()
        date_params = f"start={today-timedelta(days=89)}&end={today}&group=week"
        cases = {
            "catalog_page": "products/",
            "catalog_search": "products/?search=PERF-002",
            "report_90_days": "reports/?" + date_params,
            "insights_90_days": "insights/?" + date_params,
            "sales_page": "sales/",
        }
        results = {}
        for name, path in cases.items():
            times, counts = [], []
            for _ in range(6):
                with CaptureQueriesContext(connection) as queries:
                    start = perf_counter()
                    response = client.get(f"/api/v1/businesses/{business.id}/" + path)
                    if response.status_code != 200:
                        raise CommandError(f"{name} failed ({response.status_code}).")
                    response.render()
                    elapsed = 1000 * (perf_counter() - start)
                times.append(elapsed)
                counts.append(len(queries))
            warm = sorted(times[1:])
            results[name] = {"first_ms": round(times[0], 2), "warm_median_ms": round(median(warm), 2),
                             "warm_max_ms": round(max(warm), 2), "query_count": max(counts)}
        results["fixture"] = {"products": Product.objects.count(), "sales": Sale.objects.count(), "sale_lines": SaleLine.objects.count()}
        results["catalog_plan"] = Product.objects.filter(business=business, active=True).order_by("name", "id")[:25].explain(analyze=True)
        from pathlib import Path
        Path(options["output"]).write_text(json.dumps(results, indent=2))
        self.stdout.write(json.dumps(results, indent=2))
