"""Read-only FD renewal audit (#44): load recorded renewals and classify them.

Only SELECT queries are issued; findings are for review, never for automatic repair.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Q

from debt.models import (
    CashMovement,
    CashMovementType,
    FixedDeposit,
    FixedDepositPendingPayout,
    FixedDepositRenewalGroup,
)
from finance.fd_renewal_audit import (
    LEG_INTEREST,
    LEG_PRINCIPAL,
    LedgerMovement,
    PendingPayoutRecord,
    RenewalAuditInput,
    RenewalAuditResult,
    RenewalAuditSummary,
    SettlementRecord,
    TermRef,
    audit_renewal,
    summarize_renewal_audit,
)

_LEG_BY_MOVEMENT_TYPE = {
    CashMovementType.FD_MATURITY_PRINCIPAL: LEG_PRINCIPAL,
    CashMovementType.FD_CLOSURE_PRINCIPAL: LEG_PRINCIPAL,
    CashMovementType.FD_MATURITY_INTEREST: LEG_INTEREST,
    CashMovementType.FD_CLOSURE_INTEREST: LEG_INTEREST,
}


@dataclass(frozen=True)
class RenewalAuditReport:
    results: list[RenewalAuditResult]
    summary: RenewalAuditSummary


def _term_ref(fd: FixedDeposit) -> TermRef:
    return TermRef(
        id=fd.id,
        deposit_account_number=fd.deposit_account_number,
        institution_name=fd.institution_name,
        status=fd.status,
        principal_amount=fd.principal_amount,
        currency=fd.currency,
        interest_payout_frequency=fd.interest_payout_frequency,
        portfolio_id=fd.portfolio_id,
        bank_account_id=fd.bank_account_id,
        renewal_of_id=fd.renewal_of_id,
    )


def _ledger_movement(movement: CashMovement) -> LedgerMovement:
    return LedgerMovement(
        id=movement.id,
        leg=_LEG_BY_MOVEMENT_TYPE.get(movement.movement_type, movement.movement_type),
        direction=movement.direction,
        amount=movement.amount,
        currency=movement.currency,
        movement_date=movement.movement_date,
        linked_fixed_deposit_id=movement.linked_fixed_deposit_id,
    )


def _pending_record(pending: FixedDepositPendingPayout | None) -> PendingPayoutRecord | None:
    if pending is None:
        return None
    return PendingPayoutRecord(
        id=pending.id,
        status=pending.status,
        suggested_net_interest=pending.suggested_net_interest,
        net_interest=pending.net_interest,
        payment_date=pending.payment_date,
        movement_id=pending.cash_movement_id,
        discrepancy_status=pending.discrepancy_status,
        discrepancy_amount=pending.discrepancy_amount,
    )


def _renewal_queryset(
    *,
    user_id: int | None,
    portfolio_ids: list[int] | None,
    start_date: date | None,
    end_date: date | None,
):
    qs = FixedDepositRenewalGroup.objects.select_related(
        "old_fixed_deposit", "new_fixed_deposit", "settlement"
    )
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if portfolio_ids is not None:
        qs = qs.filter(old_fixed_deposit__portfolio_id__in=portfolio_ids)
    if start_date is not None:
        qs = qs.filter(renewal_date__gte=start_date)
    if end_date is not None:
        qs = qs.filter(renewal_date__lte=end_date)
    return qs.order_by("renewal_date", "id")


def build_renewal_audit_inputs(renewals: list[FixedDepositRenewalGroup]) -> list[RenewalAuditInput]:
    old_ids = [r.old_fixed_deposit_id for r in renewals]
    pending_by_fd = {
        p.fixed_deposit_id: p
        for p in FixedDepositPendingPayout.objects.filter(fixed_deposit_id__in=old_ids)
    }
    # Movements referenced by a settlement or payout belong to that term even when their
    # own FD link is wrong, so the audit can report the mismatch.
    referenced_owner: dict[int, int] = {}
    for renewal in renewals:
        s = renewal.settlement
        for mid in (s.principal_cash_movement_id, s.interest_cash_movement_id):
            if mid is not None:
                referenced_owner[mid] = renewal.old_fixed_deposit_id
    for pending in pending_by_fd.values():
        if pending.cash_movement_id is not None:
            referenced_owner[pending.cash_movement_id] = pending.fixed_deposit_id

    movements = CashMovement.objects.filter(
        Q(
            linked_fixed_deposit_id__in=old_ids,
            movement_type__in=list(_LEG_BY_MOVEMENT_TYPE),
        )
        | Q(id__in=list(referenced_owner))
    ).order_by("id")
    movements_by_fd: dict[int, list[LedgerMovement]] = {fd_id: [] for fd_id in old_ids}
    for movement in movements:
        owner = referenced_owner.get(movement.id, movement.linked_fixed_deposit_id)
        if owner in movements_by_fd:
            movements_by_fd[owner].append(_ledger_movement(movement))

    inputs = []
    for renewal in renewals:
        s = renewal.settlement
        inputs.append(
            RenewalAuditInput(
                renewal_id=renewal.id,
                renewal_date=renewal.renewal_date,
                currency=renewal.currency,
                old_principal=renewal.old_principal,
                direct_reinvest_amount=renewal.direct_reinvest_amount,
                cash_payout_amount=renewal.cash_payout_amount,
                gross_interest=renewal.gross_interest,
                tax_withheld=renewal.tax_withheld,
                net_interest=renewal.net_interest,
                total_maturity_value=renewal.total_maturity_value,
                old_term=_term_ref(renewal.old_fixed_deposit),
                new_term=_term_ref(renewal.new_fixed_deposit),
                settlement=SettlementRecord(
                    id=s.id,
                    fixed_deposit_id=s.fixed_deposit_id,
                    settlement_date=s.settlement_date,
                    principal_returned=s.principal_returned,
                    gross_interest=s.gross_interest,
                    tax_withheld=s.tax_withheld,
                    net_interest=s.net_interest,
                    total_net_proceeds=s.total_net_proceeds,
                    principal_movement_id=s.principal_cash_movement_id,
                    interest_movement_id=s.interest_cash_movement_id,
                ),
                movements=tuple(movements_by_fd[renewal.old_fixed_deposit_id]),
                pending_payout=_pending_record(
                    pending_by_fd.get(renewal.old_fixed_deposit_id)
                ),
            )
        )
    return inputs


def audit_fixed_deposit_renewals(
    *,
    user_id: int | None = None,
    portfolio_ids: list[int] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> RenewalAuditReport:
    """Audit recorded renewals (optionally scoped); issues only read queries."""
    renewals = list(
        _renewal_queryset(
            user_id=user_id,
            portfolio_ids=portfolio_ids,
            start_date=start_date,
            end_date=end_date,
        )
    )
    results = [audit_renewal(item) for item in build_renewal_audit_inputs(renewals)]
    return RenewalAuditReport(results=results, summary=summarize_renewal_audit(results))


def _amount(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _term_dict(term: TermRef) -> dict:
    return {
        "id": term.id,
        "deposit_account_number": term.deposit_account_number,
        "institution_name": term.institution_name,
        "status": term.status,
        "principal_amount": _amount(term.principal_amount),
        "currency": term.currency,
        "portfolio_id": term.portfolio_id,
        "bank_account_id": term.bank_account_id,
    }


def renewal_audit_report_to_dict(report: RenewalAuditReport) -> dict:
    summary = report.summary
    return {
        "read_only": True,
        "summary": {
            "renewal_count": summary.renewal_count,
            "status_counts": summary.status_counts,
            "finding_counts": summary.finding_counts,
            "totals_by_currency": [
                {
                    "currency": t.currency,
                    "renewal_count": t.renewal_count,
                    "old_principal": _amount(t.old_principal),
                    "net_interest": _amount(t.net_interest),
                    "reinvested_principal": _amount(t.reinvested_principal),
                    "cash_payout_recorded": _amount(t.cash_payout_recorded),
                    "ledger_payout_total": _amount(t.ledger_payout_total),
                    "unlinked_movement_total": _amount(t.unlinked_movement_total),
                    "pending_estimate_net": _amount(t.pending_estimate_net),
                    "confirmed_later_payout_net": _amount(t.confirmed_later_payout_net),
                }
                for t in summary.totals_by_currency
            ],
        },
        "results": [
            {
                "renewal_id": r.renewal_id,
                "renewal_date": r.renewal_date.isoformat(),
                "currency": r.currency,
                "status": r.status,
                "old_term": _term_dict(r.old_term),
                "new_term": _term_dict(r.new_term),
                "settlement_id": r.settlement_id,
                "settlement_movement_ids": list(r.settlement_movement_ids),
                "unlinked_movement_ids": list(r.unlinked_movement_ids),
                "pending_payout_id": r.pending_payout_id,
                "totals": {
                    key: _amount(getattr(r.totals, key))
                    for key in r.totals.__dataclass_fields__
                },
                "findings": [
                    {"code": f.code, "kind": f.kind, "message": f.message}
                    for f in r.findings
                ],
            }
            for r in report.results
        ],
    }
