from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("transactions", "0005_transaction_dividend_cash_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="mutualfundtransactiondetail",
            name="nav_source",
            field=models.CharField(
                choices=[
                    ("PROVIDER_CACHE", "Provider cache"),
                    ("PROVISIONAL_USER", "Provisional (user-confirmed)"),
                    ("UNKNOWN", "Unknown"),
                ],
                default="UNKNOWN",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="mutualfundtransactiondetail",
            name="provisional_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="mutualfundtransactiondetail",
            name="provisional_confirmed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="mutualfundtransactiondetail",
            name="provisional_failure_reason",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="mutualfundtransactiondetail",
            name="provisional_attempt_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
