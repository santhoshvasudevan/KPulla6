"""Fixed deposit cancellation with FD_OPENING bank ledger reversal (FD-ACC-10A)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction as db_transaction

from debt.bank_ledger_services import (
    FdOpeningAlreadyReversedError,
    create_fd_opening_reversal_cash_movement,
    fixed_deposit_has_unreversed_opening_cash_movement,
    get_unreversed_fd_opening_cash_movement,
)
from debt.models import (
    CANCEL_ELIGIBLE_FD_STATUSES,
    FixedDeposit,
    FixedDepositStatus,
)
from debt.services import FixedDepositNotFoundError, FixedDepositValidationError, get_fixed_deposit


class FixedDepositCancellationError(FixedDepositValidationError):
    """FD cannot be cancelled in its current state."""


@db_transaction.atomic
def cancel_fixed_deposit(
    user: AbstractBaseUser,
    fd_id: int,
    *,
    cancellation_date: date | None = None,
) -> FixedDeposit:
    fd = get_fixed_deposit(user, fd_id)
    if not fd.is_active:
        raise FixedDepositNotFoundError(f"Fixed deposit not found: {fd_id}")

    if fd.status == FixedDepositStatus.CANCELLED:
        raise FixedDepositCancellationError("Fixed deposit is already cancelled.")

    if fd.status not in CANCEL_ELIGIBLE_FD_STATUSES:
        raise FixedDepositCancellationError(
            "Only active or matured fixed deposits without settlement can be cancelled."
        )

    if hasattr(fd, "settlement") and fd.settlement is not None:
        raise FixedDepositCancellationError(
            "Cannot cancel a fixed deposit that has been settled."
        )

    if fd.renewals.exists():
        raise FixedDepositCancellationError(
            "Cannot cancel a fixed deposit that has been renewed."
        )

    if fd.interest_payments.exists():
        raise FixedDepositCancellationError(
            "Cannot cancel a fixed deposit with recorded interest payments."
        )

    if not fixed_deposit_has_unreversed_opening_cash_movement(fd.id):
        raise FixedDepositCancellationError(
            "This fixed deposit has no unreversed opening bank movement to reverse."
        )

    opening = get_unreversed_fd_opening_cash_movement(fd.id)
    if opening is None:
        raise FixedDepositCancellationError(
            "This fixed deposit has no unreversed opening bank movement to reverse."
        )

    effective_date = cancellation_date or date.today()
    create_fd_opening_reversal_cash_movement(
        user,
        fd,
        opening_movement=opening,
        movement_date=effective_date,
    )

    fd.status = FixedDepositStatus.CANCELLED
    fd.is_active = False
    fd.save(update_fields=["status", "is_active", "updated_at"])
    return fd
