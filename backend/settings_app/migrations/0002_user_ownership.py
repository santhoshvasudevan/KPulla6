from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

INITIAL_OWNER_EMAIL = "santhoshkgvasudevan@gmail.com"


def assign_settings_to_initial_owner(apps, schema_editor):
    User = apps.get_model("auth", "User")
    AppSettings = apps.get_model("settings_app", "AppSettings")

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

    AppSettings.objects.filter(user__isnull=True).update(user=user)


class Migration(migrations.Migration):
    dependencies = [
        ("settings_app", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portfolios", "0002_user_ownership"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="user",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="app_settings",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(assign_settings_to_initial_owner, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="appsettings",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="app_settings",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
