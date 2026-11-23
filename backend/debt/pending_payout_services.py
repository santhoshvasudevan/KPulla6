"""Pending FD maturity payout services (#45, ORM only, no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction as db_transaction
from django.utils import timezone

from debt.bank_ledger_services import (
    CashMovementValidationError,
    create_fd_settlement_cash_movement,
)
from debt.models import (
    FixedDeposit,
    FixedDepositPendingPayout,
    FixedDepositPendingPayoutStatus,
    FixedDepositSettlement,
    FixedDepositSettlementType,
    FixedDepositStatus,
)
from finance.fd_pending_payout import (
    SuggestedPayout,
    build_suggested_payout,
    classify_payout_discrepancy,
)

PENDING_PAYOUT_STATUS_FILTERS = ("pending", "confirmed", "all")


class PendingPayoutNotFoundError(Exception):
    pass


class PendingPayoutValidationError(Exception):
    pass


class PendingPayoutConflictError(Exception):
    pass


@dataclass(frozen=True)
class PendingPayoutConfirmResult:
    pending_payout: FixedDepositPendingPayout
    created: bool = True


def resolve_suggested_payout(
    gross_interest: Decimal | None,
    tax_withheld: Decimal | None,
) -> SuggestedPayout | None:
    try:
        return build_suggested_payout(gross_interest, tax_withheld)
    except ValueError as exc:
        raise PendingPayoutValidationError(str(exc)) from exc


def create_pending_payout(
    user: AbstractBaseUser,
    fd: FixedDeposit,
    *,
    origin: str,
    expected_payout_date: date | None,
    suggestion: SuggestedPayout | None,
    comment: str = "",
) -> FixedDepositPendingPayout:
    """Record an estimate only: no bank movement and no realized interest."""
    pending = FixedDepositPendingPayout(
        user=user,
        fixed_deposit=fd,
        bank_account=fd.bank_account,
        origin=origin,
        currency=fd.currency,
        expected_payout_date=expected_payout_date,
        suggested_gross_interest=suggestion.gross_interest if suggestion else None,
        suggested_tax_withheld=suggestion.tax_withheld if suggestion else None,
        suggested_net_interest=suggestion.net_interest if suggestion else None,
        comment=(comment or "").strip(),
    )
    try:
        pending.save()
    except DjangoValidationError as exc:
        raise PendingPayoutValidationError(
            exc.messages[0] if exc.messages else str(exc)
        ) from exc
    return pending


def _pending_queryset(user: AbstractBaseUser):
    return FixedDepositPendingPayout.objects.filter(user=user).select_related(
        "fixed_deposit",
        "fixed_deposit__portfolio",
        "bank_account",
    )


def get_fixed_deposit_pending_payout(
    user: AbstractBaseUser, pending_id: int
) -> FixedDepositPendingPayout:
    pending = _pending_queryset(user).filter(pk=pending_id).first()
    if pending is None:
        raise PendingPayoutNotFoundError(
            f"Fixed deposit pending payout not found: {pending_id}"
        )
    return pending


def list_fixed_deposit_pending_payouts(
    user: AbstractBaseUser,
    *,
    portfolio_ids: list[int] | None = None,
    status: str = "pending",
) -> list[FixedDepositPendingPayout]:
    if status not in PENDING_PAYOUT_STATUS_FILTERS:
        raise PendingPayoutValidationError(
            "status must be one of: pending, confirmed, all."
        )
    qs = _pending_queryset(user).exclude(
        fixed_deposit__status=FixedDepositStatus.CANCELLED
    )
    if portfolio_ids is not None:
        qs = qs.filter(fixed_deposit__portfolio_id__in=portfolio_ids)
    if status == "pending":
        qs = qs.filter(status=FixedDepositPendingPayoutStatus.PENDING)
    elif status == "confirmed":
        qs = qs.filter(status=FixedDepositPendingPayoutStatus.CONFIRMED)
    return list(qs.order_by("expected_payout_date", "created_at", "id"))


def _validate_actual_amounts(gross_interest: Decimal, tax_withheld: Decimal) -> Decimal:
    if gross_interest <= 0:
        raise PendingPayoutValidationError("gross_interest must be greater than zero.")
    if tax_withheld < 0:
        raise PendingPayoutValidationError("tax_withheld must be zero or positive.")
    if tax_withheld > gross_interest:
        raise PendingPayoutValidationError("tax_withheld cannot exceed gross_interest.")
    return gross_interest - tax_withheld


def _normalize_request_id(client_request_id: str | None) -> str | None:
    request_id = (client_request_id or "").strip() or None
    if request_id is not None and len(request_id) > 64:
        raise PendingPayoutValidationError(
            "client_request_id must be at most 64 characters."
        )
    return request_id


def _replay_for_request_id(
    user: AbstractBaseUser, request_id: str, pending_id: int
) -> FixedDepositPendingPayout | None:
    existing = _pending_queryset(user).filter(client_request_id=request_id).first()
    if existing is None:
        return None
    if existing.id != pending_id:
        raise PendingPayoutValidationError(
            "client_request_id was already used for a different pending payout."
        )
    return existing


def _confirm_locked(
    user: AbstractBaseUser,
    pending_id: int,
    *,
    payment_date: date,
    gross_interest: Decimal,
    tax_withheld: Decimal,
    net_interest: Decimal,
    comment: str,
    request_id: str | None,
) -> FixedDepositPendingPayout:
    pending = (
        FixedDepositPendingPayout.objects.select_for_update()
        .filter(user=user, pk=pending_id)
        .first()
    )
    if pending is None:
        raise PendingPayoutNotFoundError(
            f"Fixed deposit pending payout not found: {pending_id}"
        )
    if pending.status != FixedDepositPendingPayoutStatus.PENDING:
        raise PendingPayoutConflictError("This pending payout has already been confirmed.")
    fd = pending.fixed_deposit
    if fd.status == FixedDepositStatus.CANCELLED:
        raise PendingPayoutValidationError(
            "Cannot confirm a pending payout on a cancelled fixed deposit."
        )

    settlement_type = (
        FixedDepositSettlement.objects.filter(fixed_deposit=fd)
        .values_list("settlement_type", flat=True)
        .first()
        or FixedDepositSettlementType.MATURITY
    )
    note = (comment or "").strip()
    movement = None
    if net_interest > 0:
        try:
            movement = create_fd_settlement_cash_movement(
                user,
                fd,
                settlement_type=settlement_type,
                amount=net_interest,
                movement_date=payment_date,
                leg="interest",
                description=note
                or f"FD final interest payout: {fd.institution_name}/{fd.deposit_account_number}",
            )
        except CashMovementValidationError as exc:
            raise PendingPayoutValidationError(str(exc)) from exc

    discrepancy = classify_payout_discrepancy(pending.suggested_net_interest, net_interest)
    now = timezone.now()
    pending.status = FixedDepositPendingPayoutStatus.CONFIRMED
    pending.payment_date = payment_date
    pending.gross_interest = gross_interest
    pending.tax_withheld = tax_withheld
    pending.net_interest = net_interest
    pending.cash_movement = movement
    pending.client_request_id = request_id
    pending.discrepancy_status = discrepancy.status
    pending.discrepancy_amount = discrepancy.amount
    if note:
        pending.comment = note
    pending.confirmed_at = now
    pending.updated_at = now
    try:
        pending.full_clean(validate_constraints=False)
    except DjangoValidationError as exc:
        raise PendingPayoutValidationError(
            exc.messages[0] if exc.messages else str(exc)
        ) from exc

    # Conditional update guards against a concurrent confirm on backends without row locks.
    updated = FixedDepositPendingPayout.objects.filter(
        pk=pending.pk, status=FixedDepositPendingPayoutStatus.PENDING
    ).update(
        status=pending.status,
        payment_date=pending.payment_date,
        gross_interest=pending.gross_interest,
        tax_withheld=pending.tax_withheld,
        net_interest=pending.net_interest,
        cash_movement=movement,
        client_request_id=pending.client_request_id,
        discrepancy_status=pending.discrepancy_status,
        discrepancy_amount=pending.discrepancy_amount,
        comment=pending.comment,
        confirmed_at=now,
        updated_at=now,
    )
    if updated != 1:
        raise PendingPayoutConflictError("This pending payout has already been confirmed.")
    return pending


def confirm_fixed_deposit_pending_payout(
    user: AbstractBaseUser,
    pending_id: int,
    *,
    payment_date: date,
    gross_interest: Decimal,
    tax_withheld: Decimal = Decimal("0"),
    comment: str = "",
    client_request_id: str | None = None,
) -> PendingPayoutConfirmResult:
    """Record actual payout; posts one linked bank credit when net > 0.

    A mismatch against the suggestion never blocks confirmation; it is stored as an
    OPEN discrepancy for later review (#46).
    """
    net_interest = _validate_actual_amounts(gross_interest, tax_withheld)
    request_id = _normalize_request_id(client_request_id)

    if request_id is not None:
        existing = _replay_for_request_id(user, request_id, pending_id)
        if existing is not None:
            return PendingPayoutConfirmResult(pending_payout=existing, created=False)

    try:
        with db_transaction.atomic():
            _confirm_locked(
                user,
                pending_id,
                payment_date=payment_date,
                gross_interest=gross_interest,
                tax_withheld=tax_withheld,
                net_interest=net_interest,
                comment=comment,
                request_id=request_id,
            )
    except (IntegrityError, PendingPayoutConflictError):
        if request_id is None:
            raise
        # Concurrent retry with the same client_request_id — return the winner.
        existing = _replay_for_request_id(user, request_id, pending_id)
        if existing is None:
            raise
        return PendingPayoutConfirmResult(pending_payout=existing, created=False)

    return PendingPayoutConfirmResult(
        pending_payout=get_fixed_deposit_pending_payout(user, pending_id),
        created=True,
    )
