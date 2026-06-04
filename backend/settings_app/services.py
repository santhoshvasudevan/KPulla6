from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser

from settings_app.models import AppSettings, DisplayCurrency
from settings_app.seed import ensure_app_settings


def get_settings(user: AbstractBaseUser) -> AppSettings:
    return ensure_app_settings(user)


def update_settings(
    user: AbstractBaseUser,
    *,
    tax_rate_percentage: Decimal | None = None,
    display_currency: str | None = None,
) -> AppSettings:
    settings = get_settings(user)
    if tax_rate_percentage is not None:
        settings.tax_rate_percentage = tax_rate_percentage
    if display_currency is not None:
        settings.display_currency = display_currency
    settings.save()
    return settings


def is_valid_display_currency(value: str) -> bool:
    normalized = (value or "").strip().upper()
    return normalized in {c.value for c in DisplayCurrency}
