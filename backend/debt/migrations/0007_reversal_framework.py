# Generated manually for FD-ACC-10B

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("debt", "0006_fd_cancellation"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashmovement",
            name="reversal_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="fixeddepositinterestpayment",
            name="is_reversed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="fixeddepositinterestpayment",
            name="reversed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
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
                    ("FD_INTEREST_REVERSAL", "Fixed deposit interest reversal"),
                    ("FD_MATURITY_PRINCIPAL", "Fixed deposit maturity principal"),
                    ("FD_MATURITY_INTEREST", "Fixed deposit maturity interest"),
                    ("FD_CLOSURE_PRINCIPAL", "Fixed deposit closure principal"),
                    ("FD_CLOSURE_INTEREST", "Fixed deposit closure interest"),
                    ("TRANSFER_IN", "Transfer in"),
                    ("TRANSFER_OUT", "Transfer out"),
                    ("ADJUSTMENT", "Adjustment"),
                    ("REVERSAL", "Reversal"),
                ],
                max_length=32,
            ),
        ),
    ]
