from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

INITIAL_OWNER_EMAIL = "santhoshkgvasudevan@gmail.com"


def assign_existing_data_to_initial_owner(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Portfolio = apps.get_model("portfolios", "Portfolio")

    user = User.objects.filter(email__iexact=INITIAL_OWNER_EMAIL).first()
    if user is None:
        username = INITIAL_OWNER_EMAIL.split("@")[0]
        base_username = username
        suffix = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base_username}{suffix}"
            suffix += 1
        user = User.objects.create(
            username=username,
            email=INITIAL_OWNER_EMAIL,
            is_active=True,
        )

    Portfolio.objects.filter(user__isnull=True).update(user=user)


class Migration(migrations.Migration):
    dependencies = [
        ("portfolios", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="portfolio",
            name="uniq_portfolios_default",
        ),
        migrations.AddField(
            model_name="portfolio",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="portfolios",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(assign_existing_data_to_initial_owner, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="portfolio",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="portfolios",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="portfolio",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_default", True)),
                fields=("user", "is_default"),
                name="uniq_portfolios_default_per_user",
            ),
        ),
    ]
