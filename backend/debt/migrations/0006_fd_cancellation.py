# Generated manually for FD-ACC-10A

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("debt", "0005_fixed_deposit_renewal_group"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cashmovement",
            name="movement_type",
            field=models.CharField(
                choices=[
                    ("OPENING_BALANCE", "Opening balance"),
                    ("MANUAL_DEPOSIT", "Manual deposit"),
                    ("MANUAL_WITHDRAWAL", "Manual withdrawal"),
                    ("FD_OPENING", "Fixed deposit opening"),
                    ("FD_OPENING_REVERSAL", "Fixed deposit opening reversal"),
                    ("FD_INTEREST", "Fixed deposit interest"),
                    ("FD_MATURITY_PRINCIPAL", "Fixed deposit maturity principal"),
                    ("FD_MATURITY_INTEREST", "Fixed deposit maturity interest"),
                    ("FD_CLOSURE_PRINCIPAL", "Fixed deposit closure principal"),
                    ("FD_CLOSURE_INTEREST", "Fixed deposit closure interest"),
                    ("TRANSFER_IN", "Transfer in"),
                    ("TRANSFER_OUT", "Transfer out"),
                    ("ADJUSTMENT", "Adjustment"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="fixeddeposit",
            name="status",
            field=models.CharField(
                choices=[
                    ("ACTIVE", "Active"),
                    ("MATURED", "Matured"),
                    ("MATURED_SETTLED", "Matured (settled)"),
                    ("CLOSED", "Closed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="ACTIVE",
                max_length=16,
            ),
        ),
    ]
