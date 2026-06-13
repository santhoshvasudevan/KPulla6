from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0003_alter_mutualfundtransactiondetail_nav_verification_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="actual_cash_received",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=18, null=True
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="settlement_note",
            field=models.TextField(blank=True, null=True),
        ),
    ]
