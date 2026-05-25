from django.db import models


class FXRate(models.Model):
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    date = models.DateField()
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    source = models.CharField(max_length=64, default="yfinance")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fx_rates"
        indexes = [
            models.Index(fields=["from_currency", "to_currency", "date"]),
            models.Index(fields=["date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["from_currency", "to_currency", "date"],
                name="uq_fx_rates_pair_date",
            ),
        ]

    def __str__(self):
        return f"{self.from_currency}->{self.to_currency} {self.date} ({self.rate})"
