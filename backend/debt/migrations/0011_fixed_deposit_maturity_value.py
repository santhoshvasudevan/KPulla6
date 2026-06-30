from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("debt", "0010_rename_bank_accounts_user_port_idx_bank_accoun_user_id_b3da01_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="fixeddeposit",
            name="estimated_maturity_value",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=18, null=True
            ),
        ),
        migrations.AddField(
            model_name="fixeddeposit",
            name="expected_maturity_value",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=18, null=True
            ),
        ),
        migrations.AddField(
            model_name="fixeddeposit",
            name="maturity_value_source",
            field=models.CharField(
                choices=[
                    ("AUTO_ESTIMATE", "Auto estimate"),
                    ("USER_CONFIRMED", "User confirmed"),
                ],
                default="AUTO_ESTIMATE",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="fixeddeposit",
            name="maturity_estimate_method",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="fixeddeposit",
            name="maturity_value_note",
            field=models.TextField(blank=True, default=""),
        ),
    ]
