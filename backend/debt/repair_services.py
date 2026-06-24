"""One-time repair for FDs deactivated before FD-ACC-10A cancel workflow (FD-ACC-10A-REPAIR)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from django.db import transaction as db_transaction
from django.db.models import QuerySet

from debt.bank_ledger_services import (
    create_fd_opening_reversal_cash_movement,
    fixed_deposit_has_unreversed_opening_cash_movement,
    get_unreversed_fd_opening_cash_movement,
    movement_has_been_reversed,
)
from debt.models import FixedDeposit, FixedDepositStatus


DEFAULT_REPAIR_REASON = "One-time repair for FD deactivated before cancellation workflow"

_REPAIR_BLOCKED_STATUSES = frozenset(
    {
        FixedDepositStatus.CANCELLED,
        FixedDepositStatus.CLOSED,
        FixedDepositStatus.MATURED_SETTLED,
    }
)


class RepairEligibility(str, Enum):
    ELIGIBLE = "eligible"
    SKIP = "skip"


@dataclass(frozen=True)
class RepairCandidateReport:
    fixed_deposit_id: int
    user_id: int
    portfolio_id: int
    portfolio_name: str
    bank_account_id: int
    bank_account_name: str
    institution_name: str
    deposit_account_number: str
    principal_amount: str
    status: str
    is_active: bool
    opening_movement_id: int | None
    opening_amount: str | None
    opening_date: str | None
    has_interest_payments: bool
    has_settlement: bool
    has_renewal: bool
    eligibility: RepairEligibility
    skip_reason: str | None
    proposed_action: str | None


@dataclass(frozen=True)
class RepairApplyResult:
    fixed_deposit_id: int
    reversal_cash_movement_id: int
    status: str
    is_active: bool


def _fd_queryset(
    *,
    fd_id: int | None = None,
    user_id: int | None = None,
) -> QuerySet[FixedDeposit]:
    qs = (
        FixedDeposit.objects.filter(is_active=False)
        .select_related("user", "portfolio", "bank_account")
        .order_by("id")
    )
    if fd_id is not None:
        qs = qs.filter(pk=fd_id)
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    return qs


def assess_deactivated_fd_opening_repair(fd: FixedDeposit) -> RepairCandidateReport:
    """Evaluate whether an inactive FD is eligible for one-time opening reversal repair."""
    has_settlement = hasattr(fd, "settlement") and fd.settlement is not None
    has_renewal = fd.renewals.exists()
    has_interest = fd.interest_payments.exists()

    opening = get_unreversed_fd_opening_cash_movement(fd.id)
    opening_id = opening.id if opening else None
    opening_amount = str(opening.amount) if opening else None
    opening_date = opening.movement_date.isoformat() if opening else None

    base = RepairCandidateReport(
        fixed_deposit_id=fd.id,
        user_id=fd.user_id,
        portfolio_id=fd.portfolio_id,
        portfolio_name=fd.portfolio.name,
        bank_account_id=fd.bank_account_id,
        bank_account_name=fd.bank_account.name,
        institution_name=fd.institution_name,
        deposit_account_number=fd.deposit_account_number,
        principal_amount=str(fd.principal_amount),
        status=fd.status,
        is_active=fd.is_active,
        opening_movement_id=opening_id,
        opening_amount=opening_amount,
        opening_date=opening_date,
        has_interest_payments=has_interest,
        has_settlement=has_settlement,
        has_renewal=has_renewal,
        eligibility=RepairEligibility.SKIP,
        skip_reason=None,
        proposed_action=None,
    )

    if fd.is_active:
        return _skip(base, "FD is still active.")
    if fd.status in _REPAIR_BLOCKED_STATUSES:
        return _skip(base, f"FD status is {fd.status}.")
    if has_settlement:
        return _skip(base, "FD has a settlement record.")
    if has_renewal:
        return _skip(base, "FD has a renewal.")
    if has_interest:
        return _skip(
            base,
            "FD has interest payments — unsafe for automatic repair; manual review required.",
        )
    if opening is None:
        if not fixed_deposit_has_unreversed_opening_cash_movement(fd.id):
            return _skip(base, "No unreversed FD_OPENING cash movement.")
        return _skip(base, "Could not load unreversed FD_OPENING movement.")

    return RepairCandidateReport(
        **{
            **base.__dict__,
            "eligibility": RepairEligibility.ELIGIBLE,
            "proposed_action": (
                "Create FD_OPENING_REVERSAL CREDIT linked to opening movement; "
                "set status=CANCELLED; keep is_active=false."
            ),
        }
    )


def _skip(report: RepairCandidateReport, reason: str) -> RepairCandidateReport:
    return RepairCandidateReport(
        **{**report.__dict__, "eligibility": RepairEligibility.SKIP, "skip_reason": reason}
    )


def find_deactivated_fd_opening_repair_candidates(
    *,
    fd_id: int | None = None,
    user_id: int | None = None,
) -> list[RepairCandidateReport]:
    reports: list[RepairCandidateReport] = []
    for fd in _fd_queryset(fd_id=fd_id, user_id=user_id):
        reports.append(assess_deactivated_fd_opening_repair(fd))
    return reports


@db_transaction.atomic
def repair_deactivated_fd_opening(
    fd: FixedDeposit,
    *,
    reversal_date: date | None = None,
    reason: str = DEFAULT_REPAIR_REASON,
) -> RepairApplyResult:
    """Repair a single deactivated FD by reversing its unreversed FD_OPENING."""
    report = assess_deactivated_fd_opening_repair(fd)
    if report.eligibility != RepairEligibility.ELIGIBLE:
        raise ValueError(report.skip_reason or "FD is not eligible for repair.")

    opening = get_unreversed_fd_opening_cash_movement(fd.id)
    if opening is None:
        raise ValueError("No unreversed FD_OPENING cash movement.")

    effective_date = reversal_date or date.today()
    reversal = create_fd_opening_reversal_cash_movement(
        fd.user,
        fd,
        opening_movement=opening,
        movement_date=effective_date,
        reason=reason,
    )

    fd.status = FixedDepositStatus.CANCELLED
    fd.is_active = False
    fd.save(update_fields=["status", "is_active", "updated_at"])

    if not movement_has_been_reversed(opening):
        raise RuntimeError("Opening movement was not marked reversed after repair.")

    return RepairApplyResult(
        fixed_deposit_id=fd.id,
        reversal_cash_movement_id=reversal.id,
        status=fd.status,
        is_active=fd.is_active,
    )


def repair_deactivated_fd_opening_by_id(
    fd_id: int,
    *,
    reversal_date: date | None = None,
    reason: str = DEFAULT_REPAIR_REASON,
) -> RepairApplyResult:
    fd = (
        FixedDeposit.objects.filter(pk=fd_id)
        .select_related("user", "portfolio", "bank_account")
        .first()
    )
    if fd is None:
        raise ValueError(f"Fixed deposit not found: {fd_id}")
    return repair_deactivated_fd_opening(
        fd,
        reversal_date=reversal_date,
        reason=reason,
    )
