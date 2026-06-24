# Generated manually for CASH-UNIFY-1

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolios", "0004_alter_portfolio_cash_aware_enabled"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("debt", "0008_alter_cashmovement_movement_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankaccount",
            name="portfolio",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bank_accounts",
                to="portfolios.portfolio",
            ),
        ),
        migrations.AddIndex(
            model_name="bankaccount",
            index=models.Index(
                fields=["user", "portfolio"], name="bank_accounts_user_port_idx"
            ),
        ),
    ]
