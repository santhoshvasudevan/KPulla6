from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class DisplayCurrency(models.TextChoices):
    EUR = "EUR", "Euro"
    USD = "USD", "US Dollar"
    INR = "INR", "Indian Rupee"
    GBP = "GBP", "British Pound"
    CHF = "CHF", "Swiss Franc"


class AppSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="app_settings",
    )
    tax_rate_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    display_currency = models.CharField(
        max_length=3,
        choices=DisplayCurrency.choices,
        default=DisplayCurrency.EUR,
    )
    last_sync_timestamp = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "settings"
        verbose_name_plural = "app settings"

    def __str__(self):
        return f"AppSettings(display_currency={self.display_currency})"
