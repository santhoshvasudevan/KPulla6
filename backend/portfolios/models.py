from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from portfolios.constants import (
    DEFAULT_BASE_CURRENCY,
    VIRTUAL_ALL_PORTFOLIOS_NAME,
)


class Portfolio(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    base_currency = models.CharField(max_length=3, default=DEFAULT_BASE_CURRENCY)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portfolios"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["name"]),
            models.Index(fields=["is_default"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "is_default"],
                condition=models.Q(is_default=True),
                name="uniq_portfolios_default_per_user",
            ),
        ]

    def clean(self):
        super().clean()
        if self.name == VIRTUAL_ALL_PORTFOLIOS_NAME:
            raise ValidationError(
                {"name": f'"{VIRTUAL_ALL_PORTFOLIOS_NAME}" is virtual and must not be stored.'}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name
