from django.db import models


class AssetType(models.TextChoices):
    STOCK = "STOCK", "Stock"
    INDEX = "INDEX", "Index"
    ETF = "ETF", "ETF"
    FX = "FX", "FX"
    MUTUAL_FUND = "MUTUAL_FUND", "Mutual fund"


class PrimaryAssetClass(models.TextChoices):
    EQUITY = "EQUITY", "Equity"
    DEBT = "DEBT", "Debt"
    HYBRID = "HYBRID", "Hybrid"
    LIQUID = "LIQUID", "Liquid"
    COMMODITY = "COMMODITY", "Commodity"
    OTHER = "OTHER", "Other"
    UNKNOWN = "UNKNOWN", "Unknown"


class Asset(models.Model):
    asset_type = models.CharField(max_length=16, choices=AssetType.choices)
    symbol = models.CharField(max_length=32)
    display_name = models.CharField(max_length=255, blank=True, default="")
    currency = models.CharField(max_length=3, default="INR")
    provider = models.CharField(max_length=64, blank=True, default="")
    provider_symbol = models.CharField(max_length=64, blank=True, default="")
    primary_asset_class = models.CharField(
        max_length=16,
        choices=PrimaryAssetClass.choices,
        null=True,
        blank=True,
    )
    region = models.CharField(max_length=8, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assets"
        indexes = [
            models.Index(fields=["asset_type", "symbol"]),
            models.Index(fields=["is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["asset_type", "symbol"],
                name="uq_assets_type_symbol",
            ),
        ]

    def __str__(self):
        return f"{self.asset_type}:{self.symbol}"


class MutualFundProfile(models.Model):
    asset = models.OneToOneField(
        Asset,
        on_delete=models.CASCADE,
        related_name="mutual_fund_profile",
    )
    scheme_code = models.CharField(max_length=32, unique=True)
    scheme_name = models.CharField(max_length=512)
    fund_house = models.CharField(max_length=255, blank=True, default="")
    scheme_type = models.CharField(max_length=128, blank=True, default="")
    scheme_category = models.CharField(max_length=255, blank=True, default="")
    isin_growth = models.CharField(max_length=12, blank=True, default="")
    isin_reinvestment = models.CharField(max_length=12, blank=True, default="")
    direct_or_regular = models.CharField(max_length=16, blank=True, default="")
    growth_or_idcw = models.CharField(max_length=16, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mutual_fund_profiles"
        indexes = [
            models.Index(fields=["scheme_name"]),
            models.Index(fields=["fund_house"]),
        ]

    def __str__(self):
        return f"{self.scheme_code} ({self.scheme_name})"


class HistoricalPrice(models.Model):
    asset_symbol = models.CharField(max_length=32)
    date = models.DateField()
    close_price = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3)
    source = models.CharField(max_length=64, default="yfinance")
    asset_type = models.CharField(
        max_length=16,
        choices=AssetType.choices,
        default=AssetType.STOCK,
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historical_prices",
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
