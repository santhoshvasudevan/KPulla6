from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from cash.constants import SUPPORTED_CASH_CURRENCIES


class BankAccount(models.Model):
    """User-owned bank account metadata for fixed deposit linking."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bank_accounts",
    )
    portfolio = models.ForeignKey(
        "portfolios.Portfolio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_accounts",
    )
    name = models.CharField(max_length=255)
    institution_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=128)
    currency = models.CharField(max_length=3)
    opening_balance = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("0")
    )
    current_balance = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("0")
    )
    include_in_portfolio_value = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_accounts"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["user", "name"]),
            models.Index(fields=["user", "portfolio"]),
        ]

    def clean(self):
        super().clean()
        if self.portfolio_id and self.user_id:
            if self.portfolio.user_id != self.user_id:
                raise ValidationError(
                    {"portfolio": "Portfolio must belong to the same user."}
                )
            if not self.portfolio.is_active:
                raise ValidationError({"portfolio": "Portfolio must be active."})
        if self.currency and self.currency not in SUPPORTED_CASH_CURRENCIES:
            raise ValidationError(
                {"currency": f"Unsupported currency: {self.currency}"}
            )
        if not (self.name or "").strip():
            raise ValidationError({"name": "Name is required."})
        if not (self.institution_name or "").strip():
            raise ValidationError({"institution_name": "Institution name is required."})
        if not (self.account_number or "").strip():
            raise ValidationError({"account_number": "Account number is required."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.institution_name})"


class InterestPayoutFrequency(models.TextChoices):
    MONTHLY = "MONTHLY", "Monthly"
    QUARTERLY = "QUARTERLY", "Quarterly"
    HALF_YEARLY = "HALF_YEARLY", "Half yearly"
    ANNUALLY = "ANNUALLY", "Annually"
    COMPOUNDED = "COMPOUNDED", "Compounded"


class FixedDepositStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    MATURED = "MATURED", "Matured"
    MATURED_SETTLED = "MATURED_SETTLED", "Matured (settled)"
    CLOSED = "CLOSED", "Closed"
    CANCELLED = "CANCELLED", "Cancelled"


class CashMovementType(models.TextChoices):
    OPENING_BALANCE = "OPENING_BALANCE", "Opening balance"
    MANUAL_DEPOSIT = "MANUAL_DEPOSIT", "Manual deposit"
    MANUAL_WITHDRAWAL = "MANUAL_WITHDRAWAL", "Manual withdrawal"
    FD_OPENING = "FD_OPENING", "Fixed deposit opening"
    FD_OPENING_REVERSAL = "FD_OPENING_REVERSAL", "Fixed deposit opening reversal"
    FD_INTEREST = "FD_INTEREST", "Fixed deposit interest"
    FD_INTEREST_REVERSAL = "FD_INTEREST_REVERSAL", "Fixed deposit interest reversal"
    REVERSAL = "REVERSAL", "Reversal"
    FD_MATURITY_PRINCIPAL = "FD_MATURITY_PRINCIPAL", "Fixed deposit maturity principal"
    FD_MATURITY_INTEREST = "FD_MATURITY_INTEREST", "Fixed deposit maturity interest"
    FD_CLOSURE_PRINCIPAL = "FD_CLOSURE_PRINCIPAL", "Fixed deposit closure principal"
    FD_CLOSURE_INTEREST = "FD_CLOSURE_INTEREST", "Fixed deposit closure interest"
    TRANSFER_IN = "TRANSFER_IN", "Transfer in"
    TRANSFER_OUT = "TRANSFER_OUT", "Transfer out"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"


MANUAL_API_CASH_MOVEMENT_TYPES = frozenset(
    {
        CashMovementType.MANUAL_DEPOSIT,
        CashMovementType.MANUAL_WITHDRAWAL,
        CashMovementType.ADJUSTMENT,
    }
)

REVERSIBLE_MANUAL_CASH_MOVEMENT_TYPES = frozenset(
    {
        CashMovementType.MANUAL_DEPOSIT,
        CashMovementType.MANUAL_WITHDRAWAL,
        CashMovementType.ADJUSTMENT,
        CashMovementType.OPENING_BALANCE,
    }
)

INFERRED_DIRECTION_BY_TYPE = {
    CashMovementType.MANUAL_DEPOSIT: "CREDIT",
    CashMovementType.MANUAL_WITHDRAWAL: "DEBIT",
    CashMovementType.OPENING_BALANCE: "CREDIT",
    CashMovementType.FD_OPENING: "DEBIT",
    CashMovementType.FD_OPENING_REVERSAL: "CREDIT",
    CashMovementType.FD_INTEREST: "CREDIT",
    CashMovementType.FD_INTEREST_REVERSAL: "DEBIT",
    CashMovementType.FD_MATURITY_PRINCIPAL: "CREDIT",
    CashMovementType.FD_MATURITY_INTEREST: "CREDIT",
    CashMovementType.FD_CLOSURE_PRINCIPAL: "CREDIT",
    CashMovementType.FD_CLOSURE_INTEREST: "CREDIT",
}

FD_SYSTEM_MOVEMENT_TYPES = frozenset(
    {
        CashMovementType.FD_OPENING,
        CashMovementType.FD_OPENING_REVERSAL,
        CashMovementType.FD_INTEREST,
        CashMovementType.FD_INTEREST_REVERSAL,
        CashMovementType.FD_MATURITY_PRINCIPAL,
        CashMovementType.FD_MATURITY_INTEREST,
        CashMovementType.FD_CLOSURE_PRINCIPAL,
        CashMovementType.FD_CLOSURE_INTEREST,
    }
)

INTEREST_PAYMENT_BLOCKED_FD_STATUSES = frozenset(
    {FixedDepositStatus.CLOSED, FixedDepositStatus.MATURED_SETTLED}
)

SETTLEMENT_ELIGIBLE_FD_STATUSES = frozenset(
    {FixedDepositStatus.ACTIVE, FixedDepositStatus.MATURED}
)

SETTLEMENT_BLOCKED_FD_STATUSES = frozenset(
    {FixedDepositStatus.CLOSED, FixedDepositStatus.MATURED_SETTLED}
)

CANCEL_ELIGIBLE_FD_STATUSES = frozenset(
    {FixedDepositStatus.ACTIVE, FixedDepositStatus.MATURED}
)

COMPOUNDED_FD_INTEREST_WARNING = (
    "This FD is marked compounded; periodic interest payments are unusual. "
    "Confirm this is intentional."
)


class CashMovementDirection(models.TextChoices):
    CREDIT = "CREDIT", "Credit"
    DEBIT = "DEBIT", "Debit"


class CashMovementSource(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    SYSTEM = "SYSTEM", "System"


VALUE_CONTRIBUTING_STATUSES = frozenset(
    {FixedDepositStatus.ACTIVE, FixedDepositStatus.MATURED}
)


class FixedDeposit(models.Model):
    """Fixed deposit debt investment linked to a portfolio and bank account."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fixed_deposits",
    )
    portfolio = models.ForeignKey(
        "portfolios.Portfolio",
        on_delete=models.PROTECT,
        related_name="fixed_deposits",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="fixed_deposits",
    )
    institution_name = models.CharField(max_length=255)
    deposit_account_number = models.CharField(max_length=128)
    principal_amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=3)
    interest_rate_percent = models.DecimalField(max_digits=8, decimal_places=4)
    interest_payout_frequency = models.CharField(
        max_length=16, choices=InterestPayoutFrequency.choices
    )
    investment_date = models.DateField()
    maturity_date = models.DateField()
    nominee_name = models.CharField(max_length=255, blank=True, default="")
    comment = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=FixedDepositStatus.choices,
        default=FixedDepositStatus.ACTIVE,
    )
    renewal_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renewals",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fixed_deposits"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["portfolio", "is_active"]),
            models.Index(fields=["portfolio", "status"]),
            models.Index(fields=["bank_account"]),
        ]

    def clean(self):
        super().clean()
        if self.currency and self.currency not in SUPPORTED_CASH_CURRENCIES:
            raise ValidationError(
                {"currency": f"Unsupported currency: {self.currency}"}
            )
        if self.principal_amount is not None and self.principal_amount <= 0:
            raise ValidationError(
                {"principal_amount": "Principal amount must be greater than zero."}
            )
        if self.interest_rate_percent is not None and self.interest_rate_percent < 0:
            raise ValidationError(
                {"interest_rate_percent": "Interest rate must be zero or positive."}
            )
        if (
            self.investment_date
            and self.maturity_date
            and self.maturity_date <= self.investment_date
        ):
            raise ValidationError(
                {"maturity_date": "Maturity date must be after investment date."}
            )
        if not (self.institution_name or "").strip():
            raise ValidationError({"institution_name": "Institution name is required."})
        if not (self.deposit_account_number or "").strip():
            raise ValidationError(
                {"deposit_account_number": "Deposit account number is required."}
            )
        if self.bank_account_id and self.user_id:
            if self.bank_account.user_id != self.user_id:
                raise ValidationError(
                    {"bank_account": "Bank account must belong to the same user."}
                )
            if not self.bank_account.is_active:
                raise ValidationError(
                    {"bank_account": "Bank account must be active."}
                )
            if (
                self.currency
                and self.bank_account.currency
                and self.currency != self.bank_account.currency
            ):
                raise ValidationError(
                    {
                        "currency": (
                            "Fixed deposit currency must match linked bank account "
                            f"currency ({self.bank_account.currency})."
                        )
                    }
                )
        if self.portfolio_id and self.user_id:
            if self.portfolio.user_id != self.user_id:
                raise ValidationError(
                    {"portfolio": "Portfolio must belong to the same user."}
                )
            if not self.portfolio.is_active:
                raise ValidationError({"portfolio": "Portfolio must be active."})
        if self.renewal_of_id and self.user_id:
            if self.renewal_of.user_id != self.user_id:
                raise ValidationError(
                    {"renewal_of": "Renewal source must belong to the same user."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"FD {self.institution_name} {self.deposit_account_number}"


class CashMovement(models.Model):
    """Bank account cash ledger entry (user-scoped, separate from portfolio cash)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cash_movements",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="cash_movements",
    )
    portfolio = models.ForeignKey(
        "portfolios.Portfolio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_cash_movements",
    )
    movement_type = models.CharField(
        max_length=32, choices=CashMovementType.choices
    )
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    direction = models.CharField(
        max_length=8, choices=CashMovementDirection.choices
    )
    currency = models.CharField(max_length=3)
    movement_date = models.DateField()
    linked_fixed_deposit = models.ForeignKey(
        FixedDeposit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cash_movements",
    )
    description = models.TextField(blank=True, default="")
    source = models.CharField(
        max_length=16,
        choices=CashMovementSource.choices,
        default=CashMovementSource.MANUAL,
    )
    is_reversal = models.BooleanField(default=False)
    reverses = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal_rows",
    )
    reversal_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cash_movements"
        indexes = [
            models.Index(fields=["user", "bank_account"]),
            models.Index(fields=["bank_account", "movement_date"]),
            models.Index(fields=["bank_account", "movement_type"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="cash_movements_amount_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero."})
        if self.currency and self.bank_account_id:
            if self.currency != self.bank_account.currency:
                raise ValidationError(
                    {
                        "currency": (
                            "Movement currency must match bank account currency "
                            f"({self.bank_account.currency})."
                        )
                    }
                )
        if self.bank_account_id and self.user_id:
            if self.bank_account.user_id != self.user_id:
                raise ValidationError(
                    {"bank_account": "Bank account must belong to the same user."}
                )
        if self.portfolio_id and self.user_id:
            if self.portfolio.user_id != self.user_id:
                raise ValidationError(
                    {"portfolio": "Portfolio must belong to the same user."}
                )
        if self.linked_fixed_deposit_id and self.user_id:
            if self.linked_fixed_deposit.user_id != self.user_id:
                raise ValidationError(
                    {
                        "linked_fixed_deposit": (
                            "Fixed deposit must belong to the same user."
                        )
                    }
                )
            if (
                self.portfolio_id
                and self.linked_fixed_deposit.portfolio_id != self.portfolio_id
            ):
                raise ValidationError(
                    {
                        "portfolio": (
                            "Portfolio must match linked fixed deposit portfolio."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        sign = "+" if self.direction == CashMovementDirection.CREDIT else "-"
        return f"{self.movement_type} {sign}{self.amount} {self.currency}"


class FixedDepositInterestPayment(models.Model):
    """Recorded FD interest payout with gross/tax/net breakdown and ledger credit."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fixed_deposit_interest_payments",
    )
    fixed_deposit = models.ForeignKey(
        FixedDeposit,
        on_delete=models.PROTECT,
        related_name="interest_payments",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="fixed_deposit_interest_payments",
    )
    payment_date = models.DateField()
    gross_interest = models.DecimalField(max_digits=18, decimal_places=4)
    tax_withheld = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    net_interest = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=3)
    cash_movement = models.OneToOneField(
        CashMovement,
        on_delete=models.PROTECT,
        related_name="fixed_deposit_interest_payment",
    )
    comment = models.TextField(blank=True, default="")
    is_reversed = models.BooleanField(default=False)
    reversed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fixed_deposit_interest_payments"
        indexes = [
            models.Index(fields=["user", "fixed_deposit"]),
            models.Index(fields=["fixed_deposit", "payment_date"]),
            models.Index(fields=["bank_account", "payment_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(gross_interest__gt=0),
                name="fd_interest_payments_gross_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_withheld__gte=0),
                name="fd_interest_payments_tax_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(net_interest__gte=0),
                name="fd_interest_payments_net_non_negative",
            ),
        ]

    def clean(self):
        super().clean()
        if self.gross_interest is not None and self.gross_interest <= 0:
            raise ValidationError(
                {"gross_interest": "Gross interest must be greater than zero."}
            )
        if self.tax_withheld is not None and self.tax_withheld < 0:
            raise ValidationError(
                {"tax_withheld": "Tax withheld must be zero or positive."}
            )
        if self.gross_interest is not None and self.tax_withheld is not None:
            if self.tax_withheld > self.gross_interest:
                raise ValidationError(
                    {"tax_withheld": "Tax withheld cannot exceed gross interest."}
                )
            expected_net = self.gross_interest - self.tax_withheld
            if self.net_interest is not None and self.net_interest != expected_net:
                raise ValidationError(
                    {"net_interest": "Net interest must equal gross interest minus tax withheld."}
                )
        if self.currency and self.currency not in SUPPORTED_CASH_CURRENCIES:
            raise ValidationError(
                {"currency": f"Unsupported currency: {self.currency}"}
            )
        if self.fixed_deposit_id and self.user_id:
            if self.fixed_deposit.user_id != self.user_id:
                raise ValidationError(
                    {"fixed_deposit": "Fixed deposit must belong to the same user."}
                )
        if self.bank_account_id and self.user_id:
            if self.bank_account.user_id != self.user_id:
                raise ValidationError(
                    {"bank_account": "Bank account must belong to the same user."}
                )
        if self.fixed_deposit_id and self.bank_account_id:
            if self.bank_account_id != self.fixed_deposit.bank_account_id:
                raise ValidationError(
                    {
                        "bank_account": (
                            "Bank account must match the fixed deposit linked bank account."
                        )
                    }
                )
            if (
                self.currency
                and self.fixed_deposit.currency
                and self.currency != self.fixed_deposit.currency
            ):
                raise ValidationError(
                    {"currency": "Currency must match fixed deposit currency."}
                )
            if (
                self.currency
                and self.bank_account.currency
                and self.currency != self.bank_account.currency
            ):
                raise ValidationError(
                    {"currency": "Currency must match bank account currency."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"FD interest {self.net_interest} {self.currency} on {self.payment_date}"


class FixedDepositSettlementType(models.TextChoices):
    MATURITY = "MATURITY", "Maturity"
    CLOSURE = "CLOSURE", "Closure"


class FixedDepositSettlement(models.Model):
    """Recorded FD maturity or closure settlement with ledger credits."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fixed_deposit_settlements",
    )
    fixed_deposit = models.OneToOneField(
        FixedDeposit,
        on_delete=models.PROTECT,
        related_name="settlement",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="fixed_deposit_settlements",
    )
    settlement_type = models.CharField(
        max_length=16, choices=FixedDepositSettlementType.choices
    )
    settlement_date = models.DateField()
    principal_returned = models.DecimalField(max_digits=18, decimal_places=4)
    gross_interest = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    tax_withheld = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    net_interest = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    total_net_proceeds = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=3)
    principal_cash_movement = models.OneToOneField(
        CashMovement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_deposit_settlement_principal",
    )
    interest_cash_movement = models.OneToOneField(
        CashMovement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_deposit_settlement_interest",
    )
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fixed_deposit_settlements"
        indexes = [
            models.Index(fields=["user", "fixed_deposit"]),
            models.Index(fields=["bank_account", "settlement_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(principal_returned__gte=0),
                name="fd_settlements_principal_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(gross_interest__gte=0),
                name="fd_settlements_gross_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_withheld__gte=0),
                name="fd_settlements_tax_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(net_interest__gte=0),
                name="fd_settlements_net_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(total_net_proceeds__gt=0),
                name="fd_settlements_total_proceeds_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if self.principal_returned is not None and self.principal_returned < 0:
            raise ValidationError(
                {"principal_returned": "Principal returned must be zero or positive."}
            )
        if self.gross_interest is not None and self.gross_interest < 0:
            raise ValidationError(
                {"gross_interest": "Gross interest must be zero or positive."}
            )
        if self.tax_withheld is not None and self.tax_withheld < 0:
            raise ValidationError(
                {"tax_withheld": "Tax withheld must be zero or positive."}
            )
        if self.gross_interest is not None and self.tax_withheld is not None:
            if self.tax_withheld > self.gross_interest:
                raise ValidationError(
                    {"tax_withheld": "Tax withheld cannot exceed gross interest."}
                )
            expected_net = self.gross_interest - self.tax_withheld
            if self.net_interest is not None and self.net_interest != expected_net:
                raise ValidationError(
                    {
                        "net_interest": (
                            "Net interest must equal gross interest minus tax withheld."
                        )
                    }
                )
        if self.principal_returned is not None and self.net_interest is not None:
            expected_total = self.principal_returned + self.net_interest
            if (
                self.total_net_proceeds is not None
                and self.total_net_proceeds != expected_total
            ):
                raise ValidationError(
                    {
                        "total_net_proceeds": (
                            "Total net proceeds must equal principal returned plus net interest."
                        )
                    }
                )
        if self.fixed_deposit_id and self.user_id:
            if self.fixed_deposit.user_id != self.user_id:
                raise ValidationError(
                    {"fixed_deposit": "Fixed deposit must belong to the same user."}
                )
        if self.bank_account_id and self.user_id:
            if self.bank_account.user_id != self.user_id:
                raise ValidationError(
                    {"bank_account": "Bank account must belong to the same user."}
                )
        if self.fixed_deposit_id and self.bank_account_id:
            if self.bank_account_id != self.fixed_deposit.bank_account_id:
                raise ValidationError(
                    {
                        "bank_account": (
                            "Bank account must match the fixed deposit linked bank account."
                        )
                    }
                )
            if (
                self.currency
                and self.fixed_deposit.currency
                and self.currency != self.fixed_deposit.currency
            ):
                raise ValidationError(
                    {"currency": "Currency must match fixed deposit currency."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"FD settlement {self.settlement_type} {self.total_net_proceeds} {self.currency}"


class FixedDepositRenewalGroup(models.Model):
    """Audit record for FD renewal: settle old FD and open renewed FD."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fixed_deposit_renewal_groups",
    )
    old_fixed_deposit = models.ForeignKey(
        FixedDeposit,
        on_delete=models.PROTECT,
        related_name="renewal_as_old",
    )
    new_fixed_deposit = models.ForeignKey(
        FixedDeposit,
        on_delete=models.PROTECT,
        related_name="renewal_as_new",
    )
    settlement = models.OneToOneField(
        FixedDepositSettlement,
        on_delete=models.PROTECT,
        related_name="renewal_group",
    )
    renewal_date = models.DateField()
    old_principal = models.DecimalField(max_digits=18, decimal_places=4)
    direct_reinvest_amount = models.DecimalField(max_digits=18, decimal_places=4)
    cash_payout_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    gross_interest = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    tax_withheld = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    net_interest = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    total_maturity_value = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=3)
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fixed_deposit_renewal_groups"
        indexes = [
            models.Index(fields=["user", "old_fixed_deposit"]),
            models.Index(fields=["user", "new_fixed_deposit"]),
            models.Index(fields=["renewal_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(old_principal__gt=0),
                name="fd_renewal_groups_old_principal_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(direct_reinvest_amount__gt=0),
                name="fd_renewal_groups_direct_reinvest_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(cash_payout_amount__gte=0),
                name="fd_renewal_groups_cash_payout_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(gross_interest__gte=0),
                name="fd_renewal_groups_gross_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_withheld__gte=0),
                name="fd_renewal_groups_tax_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(net_interest__gte=0),
                name="fd_renewal_groups_net_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(total_maturity_value__gt=0),
                name="fd_renewal_groups_total_maturity_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if self.old_principal is not None and self.old_principal <= 0:
            raise ValidationError({"old_principal": "Old principal must be greater than zero."})
        if self.direct_reinvest_amount is not None and self.direct_reinvest_amount <= 0:
            raise ValidationError(
                {"direct_reinvest_amount": "Direct reinvest amount must be greater than zero."}
            )
        if self.cash_payout_amount is not None and self.cash_payout_amount < 0:
            raise ValidationError(
                {"cash_payout_amount": "Cash payout amount must be zero or positive."}
            )
        if self.gross_interest is not None and self.gross_interest < 0:
            raise ValidationError({"gross_interest": "Gross interest must be zero or positive."})
        if self.tax_withheld is not None and self.tax_withheld < 0:
            raise ValidationError({"tax_withheld": "Tax withheld must be zero or positive."})
        if self.gross_interest is not None and self.tax_withheld is not None:
            if self.tax_withheld > self.gross_interest:
                raise ValidationError(
                    {"tax_withheld": "Tax withheld cannot exceed gross interest."}
                )
            expected_net = self.gross_interest - self.tax_withheld
            if self.net_interest is not None and self.net_interest != expected_net:
                raise ValidationError(
                    {"net_interest": "Net interest must equal gross interest minus tax withheld."}
                )
        if self.old_fixed_deposit_id and self.user_id:
            if self.old_fixed_deposit.user_id != self.user_id:
                raise ValidationError(
                    {"old_fixed_deposit": "Old fixed deposit must belong to the same user."}
                )
        if self.new_fixed_deposit_id and self.user_id:
            if self.new_fixed_deposit.user_id != self.user_id:
                raise ValidationError(
                    {"new_fixed_deposit": "New fixed deposit must belong to the same user."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"FD renewal {self.old_fixed_deposit_id} → {self.new_fixed_deposit_id} "
            f"on {self.renewal_date}"
        )
