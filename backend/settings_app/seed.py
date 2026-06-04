from django.contrib.auth.models import AbstractBaseUser

from settings_app.models import AppSettings, DisplayCurrency


def ensure_app_settings(user: AbstractBaseUser) -> AppSettings:
    settings, _ = AppSettings.objects.get_or_create(
        user=user,
        defaults={
            "tax_rate_percentage": 0,
            "display_currency": DisplayCurrency.EUR,
        },
    )
    return settings
