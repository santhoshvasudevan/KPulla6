from django.db import models

from portfolios.constants import DEFAULT_BASE_CURRENCY


class TransactionType(models.TextChoices):
    BUY = "BUY", "Buy"
    SELL = "SELL", "Sell"
    DIVIDEND = "DIVIDEND", "Dividend"
    STOCK_SPLIT = "STOCK_SPLIT", "Stock split"


class Transaction(models.Model):
    portfolio = models.ForeignKey(
        "portfolios.Portfolio",
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    asset_symbol = models.CharField(max_length=32, db_index=True)
    date = models.DateField(db_index=True)
    type = models.CharField(max_length=16, choices=TransactionType.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=8)
    price_per_share = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    currency = models.CharField(max_length=3, default=DEFAULT_BASE_CURRENCY)
    fees = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    split_from = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    split_to = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transactions"
        indexes = [
            models.Index(fields=["portfolio", "date"]),
            models.Index(fields=["asset_symbol", "date"]),
            models.Index(fields=["portfolio", "asset_symbol"]),
        ]

    def __str__(self):
        return f"{self.type} {self.asset_symbol} @ {self.date}"
