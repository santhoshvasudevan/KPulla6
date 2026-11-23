from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("debt", "0013_alter_fixeddeposit_maturity_value_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="fixeddepositinterestpayment",
            name="client_request_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name="fixeddepositinterestpayment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("client_request_id__isnull", False)),
                fields=("user", "client_request_id"),
                name="fd_interest_payments_user_client_request_id_uniq",
            ),
        ),
    ]
