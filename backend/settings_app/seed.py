from settings_app.models import AppSettings, DisplayCurrency


def ensure_app_settings() -> AppSettings:
    settings, _ = AppSettings.objects.get_or_create(
        pk=1,
        defaults={
            "tax_rate_percentage": 0,
            "display_currency": DisplayCurrency.EUR,
        },
    )
    return settings
