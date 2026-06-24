"""Cash movement and FD interest payment reversal services (FD-ACC-10B)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction as db_transaction
from django.utils import timezone

from debt.bank_ledger_services import (
    CashMovementValidationError,
    create_cash_movement,
    get_cash_movement,
    movement_has_been_reversed,
)
from debt.interest_payment_services import (
    InterestPaymentValidationError,
    get_fixed_deposit_interest_payment,
)
from debt.models import (
    REVERSIBLE_MANUAL_CASH_MOVEMENT_TYPES,
    CashMovement,
    CashMovementDirection,
    CashMovementSource,
    CashMovementType,
    FixedDepositInterestPayment,
    FixedDepositStatus,
)


class ReversalValidationError(CashMovementValidationError):
    pass


class InterestPaymentReversalError(InterestPaymentValidationError):
    pass


@dataclass(frozen=True)
class CashMovementReversalResult:
    original: CashMovement
    reversal: CashMovement
    message: str


@dataclass(frozen=True)
class InterestPaymentReversalResult:
    payment: FixedDepositInterestPayment
    reversal_cash_movement: CashMovement
    message: str


def _opposite_direction(direction: str) -> str:
    if direction == CashMovementDirection.CREDIT:
        return CashMovementDirection.DEBIT
    return CashMovementDirection.CREDIT


def _validate_reversible_manual_movement(movement: CashMovement) -> None:
    if movement.is_reversal:
        raise ReversalValidationError("Cannot reverse a reversal movement.")
    if movement_has_been_reversed(movement):
        raise ReversalValidationError("This movement has already been reversed.")
    if movement.movement_type not in REVERSIBLE_MANUAL_CASH_MOVEMENT_TYPES:
        raise ReversalValidationError(
            "This movement type cannot be reversed through the API."
        )
    if movement.source != CashMovementSource.MANUAL:
        raise ReversalValidationError("Only manual movements can be reversed.")


@db_transaction.atomic
def reverse_cash_movement(
    user: AbstractBaseUser,
    movement_id: int,
    *,
    reversal_date: date | None = None,
    reason: str = "",
) -> CashMovementReversalResult:
    if not (reason or "").strip():
        raise ReversalValidationError("reason is required for audit.")

    movement = get_cash_movement(user, movement_id)
    _validate_reversible_manual_movement(movement)

    effective_date = reversal_date or date.today()
    opposite = _opposite_direction(movement.direction)
    trimmed_reason = reason.strip()
    description = f"Reversal: {trimmed_reason}"

    reversal = create_cash_movement(
        user,
        bank_account_id=movement.bank_account_id,
        movement_type=CashMovementType.REVERSAL,
        amount=movement.amount,
        movement_date=effective_date,
        direction=opposite,
        portfolio_id=movement.portfolio_id,
        description=description,
        source=CashMovementSource.SYSTEM,
        is_reversal=True,
        reverses_id=movement.id,
        reversal_reason=trimmed_reason,
    )

    return CashMovementReversalResult(
        original=movement,
        reversal=reversal,
        message="Cash movement reversed.",
    )


@db_transaction.atomic
def reverse_fixed_deposit_interest_payment(
    user: AbstractBaseUser,
    payment_id: int,
    *,
    reversal_date: date | None = None,
    reason: str = "",
) -> InterestPaymentReversalResult:
    if not (reason or "").strip():
        raise InterestPaymentReversalError("reason is required for audit.")

    payment = get_fixed_deposit_interest_payment(user, payment_id)

    if payment.is_reversed:
        raise InterestPaymentReversalError(
            "This interest payment has already been reversed."
        )

    fd = payment.fixed_deposit
    if fd.status == FixedDepositStatus.CANCELLED:
        raise InterestPaymentReversalError(
            "Cannot reverse interest payment on a cancelled fixed deposit."
        )

    if hasattr(fd, "settlement") and fd.settlement is not None:
        raise InterestPaymentReversalError(
            "Settlement reversal is deferred. Reverse interest before settlement, "
            "or use adjustment workflow for post-settlement corrections."
        )

    original_movement = payment.cash_movement
    if original_movement.is_reversal:
        raise InterestPaymentReversalError("Cannot reverse a reversal movement.")
    if movement_has_been_reversed(original_movement):
        raise InterestPaymentReversalError(
            "The linked cash movement has already been reversed."
        )

    effective_date = reversal_date or date.today()
    trimmed_reason = reason.strip()
    description = (
        f"Reversal of fixed deposit interest payment: {trimmed_reason}"
    )

    reversal_movement = create_cash_movement(
        user,
        bank_account_id=payment.bank_account_id,
        movement_type=CashMovementType.FD_INTEREST_REVERSAL,
        amount=payment.net_interest,
        movement_date=effective_date,
        direction=CashMovementDirection.DEBIT,
        portfolio_id=fd.portfolio_id,
        description=description,
        source=CashMovementSource.SYSTEM,
        linked_fixed_deposit_id=fd.id,
        is_reversal=True,
        reverses_id=original_movement.id,
        reversal_reason=trimmed_reason,
    )

    payment.is_reversed = True
    payment.reversed_at = timezone.now()
    payment.save(update_fields=["is_reversed", "reversed_at", "updated_at"])

    return InterestPaymentReversalResult(
        payment=payment,
        reversal_cash_movement=reversal_movement,
        message="Fixed deposit interest payment reversed.",
    )
