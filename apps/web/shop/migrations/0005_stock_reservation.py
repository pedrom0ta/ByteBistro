# Generated manually matching Django 5.0.9 schema state

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0004_order_outbox"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurant",
            name="low_stock_alert",
            field=models.BooleanField(default=True, verbose_name="Alertar estoque baixo no dashboard"),
        ),
        migrations.CreateModel(
            name="ProductIngredient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity_per_unit", models.DecimalField(decimal_places=3, max_digits=12, verbose_name="Quantidade por unidade do produto")),
                ("ingredient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="used_in", to="shop.ingredient")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recipe", to="shop.menuproduct")),
            ],
            options={
                "unique_together": {("product", "ingredient")},
            },
        ),
        migrations.CreateModel(
            name="StockReservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=12)),
                ("status", models.CharField(choices=[("active", "Ativa"), ("confirmed", "Confirmada"), ("released", "Liberada")], default="active", max_length=12)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("ingredient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="shop.ingredient")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reservations", to="shop.order")),
            ],
            options={
                "indexes": [models.Index(fields=["order", "status"], name="shop_stockres_order_status_idx")],
            },
        ),
    ]
