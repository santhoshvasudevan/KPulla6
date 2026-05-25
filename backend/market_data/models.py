from django.db import models


class AssetType(models.TextChoices):
    STOCK = "STOCK", "Stock"
    INDEX = "INDEX", "Index"
    ETF = "ETF", "ETF"
    FX = "FX", "FX"


class HistoricalPrice(models.Model):
    asset_symbol = models.CharField(max_length=32)
    date = models.DateField()
    close_price = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3)
    source = models.CharField(max_length=64, default="yfinance")
    asset_type = models.CharField(
        max_length=8,
        choices=AssetType.choices,
        default=AssetType.STOCK,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "historical_prices"
        indexes = [
            models.Index(fields=["asset_symbol", "date"]),
            models.Index(fields=["asset_type", "asset_symbol"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["asset_symbol", "date"],
                name="uq_historical_prices_asset_date",
            ),
        ]

    def __str__(self):
        return f"{self.asset_symbol} {self.date} ({self.close_price})"


class BenchmarkIndexConfig(models.Model):
    symbol = models.CharField(max_length=32, unique=True)
    display_name = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    currency = models.CharField(max_length=3, null=True, blank=True)
    source = models.CharField(max_length=64, default="yfinance")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "benchmark_index_config"
        indexes = [
            models.Index(fields=["enabled"]),
        ]

    def __str__(self):
        return f"{self.symbol} ({self.display_name})"
