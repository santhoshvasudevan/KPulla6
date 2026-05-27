from django.db import models

from portfolios.constants import DEFAULT_BASE_CURRENCY


class TransactionType(models.TextChoices):
    BUY = "BUY", "Buy"
    SELL = "SELL", "Sell"
    DIVIDEND = "DIVIDEND", "Dividend"
    STOCK_SPLIT = "STOCK_SPLIT", "Stock split"


class NavVerificationStatus(models.TextChoices):
    NOT_VERIFIED = "NOT_VERIFIED", "Not verified"
    VERIFIED = "VERIFIED", "Verified"
    NAV_MISSING = "NAV_MISSING", "NAV missing"
    NAV_MISMATCH = "NAV_MISMATCH", "NAV mismatch"
    VALUE_MISMATCH = "VALUE_MISMATCH", "Value mismatch"
    WARNING_ACCEPTED = "WARNING_ACCEPTED", "Warning accepted"
    # MF-3 legacy values (still valid on existing rows)
    OK = "OK", "OK"
    WARNING = "WARNING", "Warning"
    UNCHECKED = "UNCHECKED", "Unchecked"


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


class Folio(models.Model):
    portfolio = models.ForeignKey(
        "portfolios.Portfolio",
        on_delete=models.PROTECT,
        related_name="folios",
    )
    asset = models.ForeignKey(
        "market_data.Asset",
        on_delete=models.PROTECT,
        related_name="folios",
    )
    folio_number = models.CharField(max_length=64)
    folio_alias = models.CharField(max_length=128, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "folios"
        indexes = [
            models.Index(fields=["portfolio", "asset"]),
            models.Index(fields=["is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "asset", "folio_number"],
                name="uq_folio_portfolio_asset_number",
            ),
        ]

    def __str__(self):
        return f"{self.folio_number} ({self.portfolio_id}/{self.asset_id})"


class MutualFundTransactionDetail(models.Model):
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.CASCADE,
        related_name="mutual_fund_detail",
    )
    folio = models.ForeignKey(
        Folio,
        on_delete=models.PROTECT,
        related_name="mutual_fund_transactions",
    )
    investment_date = models.DateField()
    nav_date = models.DateField()
    nav = models.DecimalField(max_digits=18, decimal_places=6)
    units_allotted = models.DecimalField(max_digits=18, decimal_places=8)
    paid_value = models.DecimalField(max_digits=18, decimal_places=4)
    market_value = models.DecimalField(max_digits=18, decimal_places=4)
    nav_verification_status = models.CharField(
        max_length=16,
        choices=NavVerificationStatus.choices,
        default=NavVerificationStatus.NOT_VERIFIED,
    )
    nav_verification_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mutual_fund_transaction_details"
        indexes = [
            models.Index(fields=["nav_date"]),
            models.Index(fields=["investment_date"]),
        ]

    def __str__(self):
        return f"MF detail txn={self.transaction_id} folio={self.folio_id}"
