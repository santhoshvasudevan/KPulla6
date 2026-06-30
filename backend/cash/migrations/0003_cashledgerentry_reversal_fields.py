# Generated manually for CASH-CORR-1A

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cash", "0002_alter_cashledgerentry_entry_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashledgerentry",
            name="is_reversal",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="cashledgerentry",
            name="reversal_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="cashledgerentry",
            name="reverses",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reversal_rows",
                to="cash.cashledgerentry",
            ),
        ),
    ]
