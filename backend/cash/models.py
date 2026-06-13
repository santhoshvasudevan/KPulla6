from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from cash.constants import SUPPORTED_CASH_CURRENCIES
from portfolios.constants import VIRTUAL_ALL_PORTFOLIOS_NAME


class CashEntryType(models.TextChoices):
    CASH_DEPOSIT = "CASH_DEPOSIT", "Cash deposit"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL", "Cash withdrawal"
    BUY_SETTLEMENT = "BUY_SETTLEMENT", "Buy settlement"
    SELL_SETTLEMENT = "SELL_SETTLEMENT", "Sell settlement"
    TAX_WITHHELD = "TAX_WITHHELD", "Tax withheld"
    DIVIDEND_CASH = "DIVIDEND_CASH", "Dividend (cash)"
    INTEREST = "INTEREST", "Interest"
    FEE = "FEE", "Fee"
    TAX = "TAX", "Tax"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"
    TRANSFER_OUT = "TRANSFER_OUT", "Transfer out"
    TRANSFER_IN = "TRANSFER_IN", "Transfer in"
    FX_CONVERSION_OUT = "FX_CONVERSION_OUT", "FX conversion out"
    FX_CONVERSION_IN = "FX_CONVERSION_IN", "FX conversion in"


# Signed amount: positive increases cash, negative decreases cash.
POSITIVE_ENTRY_TYPES = frozenset(
    {
        CashEntryType.CASH_DEPOSIT,
        CashEntryType.SELL_SETTLEMENT,
        CashEntryType.DIVIDEND_CASH,
        CashEntryType.INTEREST,
        CashEntryType.TRANSFER_IN,
        CashEntryType.FX_CONVERSION_IN,
    }
)

NEGATIVE_ENTRY_TYPES = frozenset(
    {
        CashEntryType.CASH_WITHDRAWAL,
        CashEntryType.BUY_SETTLEMENT,
        CashEntryType.TAX_WITHHELD,
        CashEntryType.FEE,
        CashEntryType.TAX,
        CashEntryType.TRANSFER_OUT,
        CashEntryType.FX_CONVERSION_OUT,
    }
)


def validate_cash_entry_amount_sign(entry_type: str, amount: Decimal) -> None:
    if amount == 0:
        raise ValidationError({"amount": "Amount must not be zero."})
    if entry_type in POSITIVE_ENTRY_TYPES and amount <= 0:
        raise ValidationError(
            {"amount": f"{entry_type} requires a positive amount (increases cash)."}
        )
    if entry_type in NEGATIVE_ENTRY_TYPES and amount >= 0:
        raise ValidationError(
            {"amount": f"{entry_type} requires a negative amount (decreases cash)."}
        )


class CashTransferGroup(models.Model):
    """Links paired transfer / FX conversion legs (write APIs in Cash-8)."""

    date = models.DateField(db_index=True)
    source_portfolio = models.ForeignKey(
        "portfolios.Portfolio",
        on_delete=models.PROTECT,
        related_name="cash_transfers_out",
    )
    target_portfolio = models.ForeignKey(
        "portfolios.Portfolio",
        on_delete=models.PROTECT,
        related_name="cash_transfers_in",
    )
    source_currency = models.CharField(max_length=3)
    target_currency = models.CharField(max_length=3)
    source_amount = models.DecimalField(max_digits=18, decimal_places=4)
    target_amount = models.DecimalField(max_digits=18, decimal_places=4)
    user_rate = models.DecimalField(
        max_digits=18, decimal_places=8, null=True, blank=True
    )
    fees = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    fee_currency = models.CharField(max_length=3, blank=True, default="")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cash_transfer_groups"
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["source_portfolio", "date"]),
            models.Index(fields=["target_portfolio", "date"]),
        ]

    def clean(self):
        super().clean()
        if self.source_portfolio_id and self.target_portfolio_id:
            if self.source_portfolio_id == self.target_portfolio_id:
                raise ValidationError(
                    "Source and target portfolios must be different."
                )
            src_user_id = self.source_portfolio.user_id
            tgt_user_id = self.target_portfolio.user_id
            if src_user_id != tgt_user_id:
                raise ValidationError(
                    "Source and target portfolios must belong to the same user."
                )
        for field_name in ("source_currency", "target_currency"):
            code = getattr(self, field_name, None)
            if code and code not in SUPPORTED_CASH_CURRENCIES:
                raise ValidationError(
                    {field_name: f"Unsupported cash currency: {code}"}
                )
        if self.fee_currency and self.fee_currency not in SUPPORTED_CASH_CURRENCIES:
            raise ValidationError(
                {"fee_currency": f"Unsupported cash currency: {self.fee_currency}"}
            )
        if self.source_amount is not None and self.source_amount <= 0:
            raise ValidationError({"source_amount": "Must be positive."})
        if self.target_amount is not None and self.target_amount <= 0:
            raise ValidationError({"target_amount": "Must be positive."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"Transfer {self.source_portfolio_id}→{self.target_portfolio_id} "
            f"@ {self.date}"
        )


class CashLedgerEntry(models.Model):
    """
    Portfolio cash ledger row. Signed ``amount``: positive increases cash,
    negative decreases cash. Legacy portfolios may have no rows until the user adds cash.
    """

    portfolio = models.ForeignKey(
        "portfolios.Portfolio",
        on_delete=models.PROTECT,
        related_name="cash_ledger_entries",
    )
    date = models.DateField(db_index=True)
    currency = models.CharField(max_length=3)
    entry_type = models.CharField(max_length=32, choices=CashEntryType.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    source_of_funds = models.CharField(max_length=64, blank=True, default="")
    linked_transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cash_ledger_entries",
    )
    transfer_group = models.ForeignKey(
        CashTransferGroup,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cash_ledger_entries"
        indexes = [
            models.Index(fields=["portfolio", "currency", "date"]),
            models.Index(fields=["portfolio", "date"]),
            models.Index(fields=["linked_transaction"]),
        ]

    def clean(self):
        super().clean()
        if self.portfolio_id and self.portfolio.name == VIRTUAL_ALL_PORTFOLIOS_NAME:
            raise ValidationError(
                {"portfolio": f'"{VIRTUAL_ALL_PORTFOLIOS_NAME}" is virtual and cannot hold cash.'}
            )
        if self.currency and self.currency not in SUPPORTED_CASH_CURRENCIES:
            raise ValidationError(
                {"currency": f"Unsupported cash currency: {self.currency}"}
            )
        if self.entry_type and self.amount is not None:
            validate_cash_entry_amount_sign(self.entry_type, self.amount)
        if self.transfer_group_id and self.portfolio_id:
            group = self.transfer_group
            if self.portfolio_id not in (
                group.source_portfolio_id,
                group.target_portfolio_id,
            ):
                raise ValidationError(
                    {
                        "transfer_group": (
                            "Ledger entry portfolio must match transfer group "
                            "source or target portfolio."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.entry_type} {self.amount} {self.currency} @ {self.date}"
