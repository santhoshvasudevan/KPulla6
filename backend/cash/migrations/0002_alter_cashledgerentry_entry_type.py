from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cash", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cashledgerentry",
            name="entry_type",
            field=models.CharField(
                choices=[
                    ("CASH_DEPOSIT", "Cash deposit"),
                    ("CASH_WITHDRAWAL", "Cash withdrawal"),
                    ("BUY_SETTLEMENT", "Buy settlement"),
                    ("SELL_SETTLEMENT", "Sell settlement"),
                    ("TAX_WITHHELD", "Tax withheld"),
                    ("DIVIDEND_CASH", "Dividend (cash)"),
                    ("INTEREST", "Interest"),
                    ("FEE", "Fee"),
                    ("TAX", "Tax"),
                    ("ADJUSTMENT", "Adjustment"),
                    ("TRANSFER_OUT", "Transfer out"),
                    ("TRANSFER_IN", "Transfer in"),
                    ("FX_CONVERSION_OUT", "FX conversion out"),
                    ("FX_CONVERSION_IN", "FX conversion in"),
                ],
                max_length=32,
            ),
        ),
    ]
