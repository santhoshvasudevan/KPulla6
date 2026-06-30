"""Bank account cash movement ledger services (ORM only, no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
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
from finance.bank_cash import (
    BankCashMovementPoint,
    BankFundingMovementPoint,
    bank_cash_balance,
    bank_funding_balance,
    signed_movement_amount,
)
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
        current_balance: Decimal | None = None,
        available_as_of_date: Decimal | None = None,
        investment_date: date | None = None,
        latest_ledger_balance_date: date | None = None,
        bank_account_id: int | None = None,
        suggested_seed_date: date | None = None,
        suggested_seed_amount: Decimal | None = None,
    ) -> None:
        super().__init__(message)
        self.required = required
        self.available = available
        self.shortfall = shortfall
        self.currency = currency
        self.hint = hint
        self.current_balance = current_balance
        self.available_as_of_date = (
            available_as_of_date if available_as_of_date is not None else available
        )
        self.investment_date = investment_date
        self.latest_ledger_balance_date = latest_ledger_balance_date
        self.bank_account_id = bank_account_id
        self.suggested_seed_date = suggested_seed_date
        self.suggested_seed_amount = suggested_seed_amount


class OpeningBalanceAlreadySeededError(CashMovementValidationError):
    pass


class DuplicateHistoricalSeedError(CashMovementValidationError):
    def __init__(self, message: str, *, existing_movement: CashMovement) -> None:
        super().__init__(message)
        self.existing_movement = existing_movement


class FdOpeningAlreadyRecordedError(CashMovementValidationError):
    pass


class FdOpeningAlreadyReversedError(CashMovementValidationError):
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


def _funding_movement_points_for_account(bank_account_id: int) -> list[BankFundingMovementPoint]:
    reversed_ids = set(
        CashMovement.objects.filter(
            bank_account_id=bank_account_id,
            is_reversal=True,
            reverses_id__isnull=False,
        ).values_list("reverses_id", flat=True)
    )
    rows = CashMovement.objects.filter(bank_account_id=bank_account_id).only(
        "id",
        "movement_date",
        "currency",
        "amount",
        "direction",
        "is_reversal",
    )
    return [
        BankFundingMovementPoint(
            movement_date=row.movement_date,
            currency=row.currency,
            amount=row.amount,
            direction=row.direction,
            is_reversal=row.is_reversal,
            is_reversed=row.id in reversed_ids,
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


def compute_bank_funding_balance(
    bank_account: BankAccount | int,
    *,
    as_of_date: date | None = None,
) -> Decimal:
    """As-of balance for FD funding validation and FD seed UI."""
    account_id = bank_account.id if isinstance(bank_account, BankAccount) else bank_account
    return bank_funding_balance(
        _funding_movement_points_for_account(account_id),
        as_of_date=as_of_date,
    )


def suggested_seed_date_for_fd(investment_date: date) -> date:
    """Default historical seed date: day before investment date to avoid same-day ordering."""
    return investment_date - timedelta(days=1)


def latest_ledger_movement_date(bank_account: BankAccount | int) -> date | None:
    account_id = bank_account.id if isinstance(bank_account, BankAccount) else bank_account
    return (
        CashMovement.objects.filter(bank_account_id=account_id)
        .order_by("-movement_date", "-id")
        .values_list("movement_date", flat=True)
        .first()
    )


def bank_account_has_ledger(bank_account: BankAccount | int) -> bool:
    account_id = bank_account.id if isinstance(bank_account, BankAccount) else bank_account
    return CashMovement.objects.filter(bank_account_id=account_id).exists()


def fixed_deposit_has_opening_cash_movement(fixed_deposit_id: int) -> bool:
    return fixed_deposit_has_unreversed_opening_cash_movement(fixed_deposit_id)


def fixed_deposit_has_unreversed_opening_cash_movement(fixed_deposit_id: int) -> bool:
    opening = (
        CashMovement.objects.filter(
            linked_fixed_deposit_id=fixed_deposit_id,
            movement_type=CashMovementType.FD_OPENING,
            is_reversal=False,
        )
        .order_by("id")
        .first()
    )
    if opening is None:
        return False
    return not CashMovement.objects.filter(
        reverses_id=opening.id,
        is_reversal=True,
    ).exists()


def get_unreversed_fd_opening_cash_movement(fixed_deposit_id: int) -> CashMovement | None:
    opening = (
        CashMovement.objects.filter(
            linked_fixed_deposit_id=fixed_deposit_id,
            movement_type=CashMovementType.FD_OPENING,
            is_reversal=False,
        )
        .order_by("id")
        .first()
    )
    if opening is None:
        return None
    if CashMovement.objects.filter(reverses_id=opening.id, is_reversal=True).exists():
        return None
    return opening


def get_fd_opening_cash_movement_id(fixed_deposit_id: int) -> int | None:
    opening = get_unreversed_fd_opening_cash_movement(fixed_deposit_id)
    return opening.id if opening else None


def movement_has_been_reversed(movement: CashMovement | int) -> bool:
    movement_id = movement.id if isinstance(movement, CashMovement) else movement
    return CashMovement.objects.filter(
        reverses_id=movement_id,
        is_reversal=True,
    ).exists()


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
    for_funding: bool = False,
) -> None:
    if for_funding:
        available = compute_bank_funding_balance(bank_account, as_of_date=as_of_date)
    else:
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
    reversal_reason: str = "",
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

    if movement_type == CashMovementType.FD_OPENING_REVERSAL:
        if source != CashMovementSource.SYSTEM:
            raise CashMovementValidationError(
                "FD_OPENING_REVERSAL movements must use SYSTEM source."
            )
        if linked_fixed_deposit_id is None:
            raise CashMovementValidationError(
                "FD_OPENING_REVERSAL movements must link to a fixed deposit."
            )
        if portfolio_id is None:
            raise CashMovementValidationError(
                "FD_OPENING_REVERSAL movements must include portfolio_id."
            )
        if not is_reversal:
            raise CashMovementValidationError(
                "FD_OPENING_REVERSAL movements must be marked as reversals."
            )
        if reverses_id is None:
            raise CashMovementValidationError(
                "FD_OPENING_REVERSAL movements must reference the opening movement."
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

    if movement_type == CashMovementType.FD_INTEREST_REVERSAL:
        if source != CashMovementSource.SYSTEM:
            raise CashMovementValidationError(
                "FD_INTEREST_REVERSAL movements must use SYSTEM source."
            )
        if linked_fixed_deposit_id is None:
            raise CashMovementValidationError(
                "FD_INTEREST_REVERSAL movements must link to a fixed deposit."
            )
        if portfolio_id is None:
            raise CashMovementValidationError(
                "FD_INTEREST_REVERSAL movements must include portfolio_id."
            )
        if not is_reversal:
            raise CashMovementValidationError(
                "FD_INTEREST_REVERSAL movements must be marked as reversals."
            )
        if reverses_id is None:
            raise CashMovementValidationError(
                "FD_INTEREST_REVERSAL movements must reference the interest movement."
            )

    if movement_type == CashMovementType.REVERSAL:
        if source != CashMovementSource.SYSTEM:
            raise CashMovementValidationError(
                "REVERSAL movements must use SYSTEM source."
            )
        if not is_reversal:
            raise CashMovementValidationError(
                "REVERSAL movements must be marked as reversals."
            )
        if reverses_id is None:
            raise CashMovementValidationError(
                "REVERSAL movements must reference the original movement."
            )

    if movement_type in FD_SYSTEM_MOVEMENT_TYPES - {
        CashMovementType.FD_OPENING,
        CashMovementType.FD_OPENING_REVERSAL,
        CashMovementType.FD_INTEREST,
        CashMovementType.FD_INTEREST_REVERSAL,
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
        if (
            movement_type == CashMovementType.FD_OPENING_REVERSAL
            and reverses.movement_type != CashMovementType.FD_OPENING
        ):
            raise CashMovementValidationError(
                "FD_OPENING_REVERSAL must reference an FD_OPENING movement."
            )
        if (
            movement_type == CashMovementType.FD_INTEREST_REVERSAL
            and reverses.movement_type != CashMovementType.FD_INTEREST
        ):
            raise CashMovementValidationError(
                "FD_INTEREST_REVERSAL must reference an FD_INTEREST movement."
            )
        if CashMovement.objects.filter(reverses_id=reverses.id, is_reversal=True).exists():
            raise FdOpeningAlreadyReversedError(
                "A reversal already exists for this opening movement."
            )

    signed = signed_movement_amount(amount, resolved_direction)
    use_funding_balance = (
        movement_type == CashMovementType.FD_OPENING and not is_reversal
    )
    validate_no_overdraft(
        account,
        additional_signed=signed,
        as_of_date=movement_date,
        for_funding=use_funding_balance,
    )

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
        reversal_reason=(reversal_reason or "").strip(),
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


def create_fd_opening_reversal_cash_movement(
    user: AbstractBaseUser,
    fd: FixedDeposit,
    *,
    opening_movement: CashMovement,
    movement_date: date,
    reason: str = "",
) -> CashMovement:
    if opening_movement.movement_type != CashMovementType.FD_OPENING:
        raise CashMovementValidationError(
            "Opening reversal must reference an FD_OPENING movement."
        )
    if opening_movement.linked_fixed_deposit_id != fd.id:
        raise CashMovementValidationError(
            "Opening movement does not belong to this fixed deposit."
        )
    description = (
        "Cancellation reversal of fixed deposit opening: "
        f"{fd.institution_name}/{fd.deposit_account_number}"
    )
    trimmed_reason = (reason or "").strip()
    if trimmed_reason:
        description = f"{description} — {trimmed_reason}"
    return create_cash_movement(
        user,
        bank_account_id=fd.bank_account_id,
        movement_type=CashMovementType.FD_OPENING_REVERSAL,
        amount=opening_movement.amount,
        movement_date=movement_date,
        direction=CashMovementDirection.CREDIT,
        portfolio_id=fd.portfolio_id,
        description=description,
        source=CashMovementSource.SYSTEM,
        linked_fixed_deposit_id=fd.id,
        is_reversal=True,
        reverses_id=opening_movement.id,
        reversal_reason=trimmed_reason,
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


HISTORICAL_FD_SEED_DEFAULT_REASON = "Historical balance seed for FD creation"


def _find_duplicate_historical_seed(
    bank_account_id: int,
    *,
    movement_date: date,
    amount: Decimal,
    reason: str,
) -> CashMovement | None:
    normalized_reason = (reason or HISTORICAL_FD_SEED_DEFAULT_REASON).strip()
    return (
        CashMovement.objects.filter(
            bank_account_id=bank_account_id,
            movement_type=CashMovementType.MANUAL_DEPOSIT,
            movement_date=movement_date,
            amount=amount,
            direction=CashMovementDirection.CREDIT,
            is_reversal=False,
            description__startswith=normalized_reason,
        )
        .order_by("id")
        .first()
    )


@dataclass(frozen=True)
class HistoricalBankBalanceSeedResult:
    movement: CashMovement
    balance_as_of_date: Decimal
    as_of_date: date
    currency: str


@db_transaction.atomic
def seed_historical_bank_balance(
    user: AbstractBaseUser,
    bank_account_id: int,
    *,
    movement_date: date,
    amount: Decimal,
    reason: str = "",
    note: str = "",
) -> HistoricalBankBalanceSeedResult:
    """Explicit MANUAL_DEPOSIT to fund a backdated FD; does not create portfolio holdings."""
    account = get_bank_account(user, bank_account_id)
    if not account.is_active:
        raise CashMovementValidationError("Bank account must be active.")

    description = (reason or HISTORICAL_FD_SEED_DEFAULT_REASON).strip()
    if note.strip():
        description = f"{description} — {note.strip()}"

    duplicate = _find_duplicate_historical_seed(
        account.id,
        movement_date=movement_date,
        amount=amount,
        reason=reason or HISTORICAL_FD_SEED_DEFAULT_REASON,
    )
    if duplicate is not None:
        raise DuplicateHistoricalSeedError(
            "A similar historical seed already exists for this bank account, date, and amount.",
            existing_movement=duplicate,
        )

    movement = create_cash_movement(
        user,
        bank_account_id=bank_account_id,
        movement_type=CashMovementType.MANUAL_DEPOSIT,
        amount=amount,
        movement_date=movement_date,
        description=description,
        portfolio_id=None,
    )
    balance_as_of = compute_bank_funding_balance(account, as_of_date=movement_date)
    return HistoricalBankBalanceSeedResult(
        movement=movement,
        balance_as_of_date=balance_as_of,
        as_of_date=movement_date,
        currency=account.currency,
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
        .select_related("bank_account", "portfolio", "reverses")
        .prefetch_related("reversal_rows")
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
