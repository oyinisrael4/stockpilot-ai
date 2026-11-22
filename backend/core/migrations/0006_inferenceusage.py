from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0005_product_product_catalog_order")]
    operations = [migrations.CreateModel(name="InferenceUsage", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("key", models.CharField(max_length=80, unique=True)),
        ("units", models.PositiveIntegerField(default=0)),
    ])]
