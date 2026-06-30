from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("debt", "0011_fixed_deposit_maturity_value"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fixeddeposit",
            name="maturity_value_source",
            field=models.CharField(
                choices=[
                    ("AUTO_ESTIMATE", "Auto estimate"),
                    ("AUTO_PRINCIPAL", "Auto principal"),
                    ("USER_CONFIRMED", "User confirmed"),
                ],
                default="AUTO_ESTIMATE",
                max_length=20,
            ),
        ),
    ]
