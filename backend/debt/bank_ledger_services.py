"""Bank account cash movement ledger services (ORM only, no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction as db_transaction
from django.db.models import QuerySet

from debt.models import (
    FD_SYSTEM_MOVEMENT_TYPES,
    INFERRED_DIRECTION_BY_TYPE,
    MANUAL_API_CASH_MOVEMENT_TYPES,
    BankAccount,
    CashMovement,
    CashMovementDirection,
    CashMovementSource,
    CashMovementType,
    FixedDeposit,
    FixedDepositSettlementType,
)
from finance.bank_cash import BankCashMovementPoint, bank_cash_balance, signed_movement_amount
from portfolios.services import PortfolioNotFoundError, get_portfolio

from debt.services import (
    BankAccountNotFoundError,
    BankAccountValidationError,
    get_bank_account,
)


class CashMovementNotFoundError(Exception):
    pass


class CashMovementValidationError(Exception):
    pass


class InsufficientBankBalanceError(CashMovementValidationError):
    def __init__(
        self,
        message: str,
        *,
        required: Decimal,
        available: Decimal,
        shortfall: Decimal,
        currency: str,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.required = required
        self.available = available
        self.shortfall = shortfall
        self.currency = currency
        self.hint = hint


class OpeningBalanceAlreadySeededError(CashMovementValidationError):
    pass


class FdOpeningAlreadyRecordedError(CashMovementValidationError):
    pass


IMMUTABLE_FD_FIELDS_AFTER_OPENING = frozenset(
    {
        "principal_amount",
        "bank_account_id",
        "currency",
        "investment_date",
        "portfolio_id",
    }
)


@dataclass(frozen=True)
class CashMovementListResult:
    items: list[CashMovement]
    total: int
    page: int
    page_size: int
    pages: int


def _movement_points_for_account(bank_account_id: int) -> list[BankCashMovementPoint]:
    rows = CashMovement.objects.filter(bank_account_id=bank_account_id).only(
        "movement_date", "currency", "amount", "direction"
    )
    return [
        BankCashMovementPoint(
            movement_date=row.movement_date,
            currency=row.currency,
            amount=row.amount,
            direction=row.direction,
        )
        for row in rows
    ]


def compute_bank_account_balance(
    bank_account: BankAccount | int,
    *,
    as_of_date: date | None = None,
) -> Decimal:
    account_id = bank_account.id if isinstance(bank_account, BankAccount) else bank_account
    return bank_cash_balance(_movement_points_for_account(account_id), as_of_date=as_of_date)


def bank_account_has_ledger(bank_account: BankAccount | int) -> bool:
    account_id = bank_account.id if isinstance(bank_account, BankAccount) else bank_account
    return CashMovement.objects.filter(bank_account_id=account_id).exists()


def fixed_deposit_has_opening_cash_movement(fixed_deposit_id: int) -> bool:
    return CashMovement.objects.filter(
        linked_fixed_deposit_id=fixed_deposit_id,
        movement_type=CashMovementType.FD_OPENING,
        is_reversal=False,
    ).exists()


def get_fd_opening_cash_movement_id(fixed_deposit_id: int) -> int | None:
    return (
        CashMovement.objects.filter(
            linked_fixed_deposit_id=fixed_deposit_id,
            movement_type=CashMovementType.FD_OPENING,
            is_reversal=False,
        )
        .values_list("id", flat=True)
        .first()
    )


def opening_balance_is_seeded(bank_account: BankAccount | int) -> bool:
    account_id = bank_account.id if isinstance(bank_account, BankAccount) else bank_account
    return CashMovement.objects.filter(
        bank_account_id=account_id,
        movement_type=CashMovementType.OPENING_BALANCE,
        is_reversal=False,
    ).exists()


def refresh_bank_account_balance(bank_account: BankAccount) -> Decimal:
    balance = compute_bank_account_balance(bank_account)
    bank_account.current_balance = balance
    bank_account.save(update_fields=["current_balance", "updated_at"])
    return balance


def validate_no_overdraft(
    bank_account: BankAccount,
    *,
    additional_signed: Decimal,
    as_of_date: date | None = None,
) -> None:
    available = compute_bank_account_balance(bank_account, as_of_date=as_of_date)
    projected = available + additional_signed
    if projected >= Decimal("0"):
        return
    required = abs(additional_signed) if additional_signed < 0 else Decimal("0")
    shortfall = abs(projected)
    raise InsufficientBankBalanceError(
        "Insufficient bank account balance for this movement.",
        required=required,
        available=available,
        shortfall=shortfall,
        currency=bank_account.currency,
    )


def _resolve_portfolio(user: AbstractBaseUser, portfolio_id: int | None):
    if portfolio_id is None:
        return None
    try:
        portfolio = get_portfolio(user, portfolio_id)
    except PortfolioNotFoundError as exc:
        raise CashMovementValidationError(str(exc)) from exc
    if not portfolio.is_active:
        raise CashMovementValidationError(f"Portfolio is inactive: {portfolio_id}")
    return portfolio


def _validate_opening_balance_unique(bank_account: BankAccount) -> None:
    if opening_balance_is_seeded(bank_account):
        raise OpeningBalanceAlreadySeededError(
            "Opening balance has already been seeded for this bank account."
        )


@db_transaction.atomic
def create_cash_movement(
    user: AbstractBaseUser,
    *,
    bank_account_id: int,
    movement_type: str,
    amount: Decimal,
    movement_date: date,
    direction: str | None = None,
    portfolio_id: int | None = None,
    description: str = "",
    source: str = CashMovementSource.MANUAL,
    linked_fixed_deposit_id: int | None = None,
    is_reversal: bool = False,
    reverses_id: int | None = None,
) -> CashMovement:
    if source != CashMovementSource.MANUAL and movement_type in MANUAL_API_CASH_MOVEMENT_TYPES:
        raise CashMovementValidationError(
            "Manual movement types must use MANUAL source through the public API."
        )

    if movement_type == CashMovementType.OPENING_BALANCE and not is_reversal:
        pass  # validated after account load

    account = get_bank_account(user, bank_account_id)
    if not account.is_active:
        raise CashMovementValidationError("Bank account must be active.")

    if movement_type == CashMovementType.OPENING_BALANCE and not is_reversal:
        _validate_opening_balance_unique(account)

    if movement_type == CashMovementType.FD_OPENING:
        if source != CashMovementSource.SYSTEM:
            raise CashMovementValidationError(
                "FD_OPENING movements must use SYSTEM source."
            )
        if linked_fixed_deposit_id is None:
            raise CashMovementValidationError(
                "FD_OPENING movements must link to a fixed deposit."
            )
        if portfolio_id is None:
            raise CashMovementValidationError(
                "FD_OPENING movements must include portfolio_id."
            )

    if movement_type == CashMovementType.FD_INTEREST:
        if source != CashMovementSource.SYSTEM:
            raise CashMovementValidationError(
                "FD_INTEREST movements must use SYSTEM source."
            )
        if linked_fixed_deposit_id is None:
            raise CashMovementValidationError(
                "FD_INTEREST movements must link to a fixed deposit."
            )
        if portfolio_id is None:
            raise CashMovementValidationError(
                "FD_INTEREST movements must include portfolio_id."
            )

    if movement_type in FD_SYSTEM_MOVEMENT_TYPES - {
        CashMovementType.FD_OPENING,
        CashMovementType.FD_INTEREST,
    }:
        if source != CashMovementSource.SYSTEM:
            raise CashMovementValidationError(
                f"{movement_type} movements must use SYSTEM source."
            )
        if linked_fixed_deposit_id is None:
            raise CashMovementValidationError(
                f"{movement_type} movements must link to a fixed deposit."
            )
        if portfolio_id is None:
            raise CashMovementValidationError(
                f"{movement_type} movements must include portfolio_id."
            )

    if amount <= 0:
        raise CashMovementValidationError("amount must be greater than zero.")

    resolved_direction = direction
    if resolved_direction is None:
        inferred = INFERRED_DIRECTION_BY_TYPE.get(movement_type)
        if inferred is None:
            raise CashMovementValidationError("direction is required for this movement type.")
        resolved_direction = inferred

    if resolved_direction not in (
        CashMovementDirection.CREDIT,
        CashMovementDirection.DEBIT,
    ):
        raise CashMovementValidationError("direction must be CREDIT or DEBIT.")

    portfolio = _resolve_portfolio(user, portfolio_id)

    linked_fd = None
    if linked_fixed_deposit_id is not None:
        from debt.services import get_fixed_deposit

        linked_fd = get_fixed_deposit(user, linked_fixed_deposit_id)
        if (
            movement_type == CashMovementType.FD_OPENING
            and not is_reversal
            and fixed_deposit_has_opening_cash_movement(linked_fd.id)
        ):
            raise FdOpeningAlreadyRecordedError(
                "FD opening cash movement already exists for this fixed deposit."
            )

    reverses = None
    if reverses_id is not None:
        reverses = get_cash_movement(user, reverses_id)

    signed = signed_movement_amount(amount, resolved_direction)
    validate_no_overdraft(account, additional_signed=signed, as_of_date=movement_date)

    movement = CashMovement(
        user=user,
        bank_account=account,
        portfolio=portfolio,
        movement_type=movement_type,
        amount=amount,
        direction=resolved_direction,
        currency=account.currency,
        movement_date=movement_date,
        linked_fixed_deposit=linked_fd,
        description=(description or "").strip(),
        source=source,
        is_reversal=is_reversal,
        reverses=reverses,
    )
    movement.save()
    refresh_bank_account_balance(account)
    return movement


def create_manual_cash_movement(
    user: AbstractBaseUser,
    *,
    bank_account_id: int,
    movement_type: str,
    amount: Decimal,
    movement_date: date,
    direction: str | None = None,
    portfolio_id: int | None = None,
    description: str = "",
) -> CashMovement:
    if movement_type not in MANUAL_API_CASH_MOVEMENT_TYPES:
        raise CashMovementValidationError(
            f"Movement type {movement_type} is not allowed through the manual API."
        )
    if movement_type == CashMovementType.ADJUSTMENT and direction is None:
        raise CashMovementValidationError("direction is required for ADJUSTMENT movements.")

    return create_cash_movement(
        user,
        bank_account_id=bank_account_id,
        movement_type=movement_type,
        amount=amount,
        movement_date=movement_date,
        direction=direction,
        portfolio_id=portfolio_id,
        description=description,
        source=CashMovementSource.MANUAL,
    )


def create_fd_opening_cash_movement(
    user: AbstractBaseUser,
    fd: FixedDeposit,
) -> CashMovement:
    description = (
        f"Fixed deposit opening: {fd.institution_name}/{fd.deposit_account_number}"
    )
    return create_cash_movement(
        user,
        bank_account_id=fd.bank_account_id,
        movement_type=CashMovementType.FD_OPENING,
        amount=fd.principal_amount,
        movement_date=fd.investment_date,
        direction=CashMovementDirection.DEBIT,
        portfolio_id=fd.portfolio_id,
        description=description,
        source=CashMovementSource.SYSTEM,
        linked_fixed_deposit_id=fd.id,
    )


def create_fd_interest_cash_movement(
    user: AbstractBaseUser,
    fd: FixedDeposit,
    *,
    net_interest: Decimal,
    payment_date: date,
    description: str = "",
) -> CashMovement:
    if net_interest <= 0:
        raise CashMovementValidationError("net_interest must be greater than zero.")
    if not description:
        description = (
            f"Fixed deposit interest: {fd.institution_name}/{fd.deposit_account_number}"
        )
    return create_cash_movement(
        user,
        bank_account_id=fd.bank_account_id,
        movement_type=CashMovementType.FD_INTEREST,
        amount=net_interest,
        movement_date=payment_date,
        direction=CashMovementDirection.CREDIT,
        portfolio_id=fd.portfolio_id,
        description=description,
        source=CashMovementSource.SYSTEM,
        linked_fixed_deposit_id=fd.id,
    )


def _settlement_principal_movement_type(settlement_type: str) -> str:
    if settlement_type == FixedDepositSettlementType.MATURITY:
        return CashMovementType.FD_MATURITY_PRINCIPAL
    return CashMovementType.FD_CLOSURE_PRINCIPAL


def _settlement_interest_movement_type(settlement_type: str) -> str:
    if settlement_type == FixedDepositSettlementType.MATURITY:
        return CashMovementType.FD_MATURITY_INTEREST
    return CashMovementType.FD_CLOSURE_INTEREST


def create_fd_settlement_cash_movement(
    user: AbstractBaseUser,
    fd: FixedDeposit,
    *,
    settlement_type: str,
    amount: Decimal,
    movement_date: date,
    leg: str,
    description: str = "",
) -> CashMovement:
    if amount <= 0:
        raise CashMovementValidationError(f"{leg} settlement amount must be greater than zero.")
    if leg == "principal":
        movement_type = _settlement_principal_movement_type(settlement_type)
        default_desc = (
            f"Fixed deposit {settlement_type.lower()} principal: "
            f"{fd.institution_name}/{fd.deposit_account_number}"
        )
    elif leg == "interest":
        movement_type = _settlement_interest_movement_type(settlement_type)
        default_desc = (
            f"Fixed deposit {settlement_type.lower()} interest: "
            f"{fd.institution_name}/{fd.deposit_account_number}"
        )
    else:
        raise CashMovementValidationError(f"Unknown settlement leg: {leg}")
    if not description:
        description = default_desc
    return create_cash_movement(
        user,
        bank_account_id=fd.bank_account_id,
        movement_type=movement_type,
        amount=amount,
        movement_date=movement_date,
        direction=CashMovementDirection.CREDIT,
        portfolio_id=fd.portfolio_id,
        description=description,
        source=CashMovementSource.SYSTEM,
        linked_fixed_deposit_id=fd.id,
    )


@db_transaction.atomic
def seed_opening_balance(
    user: AbstractBaseUser,
    bank_account_id: int,
    *,
    movement_date: date | None = None,
) -> CashMovement:
    account = get_bank_account(user, bank_account_id)
    if not account.is_active:
        raise BankAccountNotFoundError(f"Bank account not found: {bank_account_id}")

    if account.opening_balance <= 0:
        raise CashMovementValidationError(
            "Opening balance must be greater than zero to seed the ledger."
        )

    _validate_opening_balance_unique(account)

    effective_date = movement_date or date.today()
    return create_cash_movement(
        user,
        bank_account_id=bank_account_id,
        movement_type=CashMovementType.OPENING_BALANCE,
        amount=account.opening_balance,
        movement_date=effective_date,
        direction=CashMovementDirection.CREDIT,
        description="Opening balance seed",
        source=CashMovementSource.MANUAL,
    )


def get_cash_movement(user: AbstractBaseUser, movement_id: int) -> CashMovement:
    movement = (
        CashMovement.objects.filter(user=user, pk=movement_id)
        .select_related("bank_account", "portfolio", "linked_fixed_deposit")
        .first()
    )
    if not movement:
        raise CashMovementNotFoundError(f"Cash movement not found: {movement_id}")
    return movement


def list_cash_movements(
    user: AbstractBaseUser,
    *,
    bank_account_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> CashMovementListResult:
    qs: QuerySet[CashMovement] = (
        CashMovement.objects.filter(user=user)
        .select_related("bank_account", "portfolio")
        .order_by("-movement_date", "-created_at", "-id")
    )
    if bank_account_id is not None:
        qs = qs.filter(bank_account_id=bank_account_id)

    total = qs.count()
    page_size = max(1, min(page_size, 100))
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page = max(1, min(page, pages))
    offset = (page - 1) * page_size
    items = list(qs[offset : offset + page_size])
    return CashMovementListResult(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def bank_account_ledger_metadata(account: BankAccount) -> dict:
    has_ledger = bank_account_has_ledger(account)
    return {
        "has_ledger_entries": has_ledger,
        "opening_balance_seeded": opening_balance_is_seeded(account),
        "balance_source": "ledger" if has_ledger else "manual",
    }
