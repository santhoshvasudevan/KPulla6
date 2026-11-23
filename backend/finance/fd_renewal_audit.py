"""Pure read-only audit of recorded FD renewals against the #43 allocation rules (#44).

Each renewal is classified as:

- ``CONSISTENT`` — recorded principal, final net interest, reinvested principal,
  cash payout, and linked bank credits agree with the direct-renewal rules.
- ``INCONSISTENT`` — the recorded data contradicts itself (a confirmed problem).
- ``INCOMPLETE`` — no contradiction was found, but evidence is missing or ambiguous
  (for example final interest still pending, or a payout with no linked credit).

Pending interest estimates are never counted as settled proceeds.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from finance.fd_renewal_allocation import allocate_renewal_proceeds

_ZERO = Decimal("0")

STATUS_CONSISTENT = "CONSISTENT"
STATUS_INCONSISTENT = "INCONSISTENT"
STATUS_INCOMPLETE = "INCOMPLETE"
AUDIT_STATUSES = (STATUS_CONSISTENT, STATUS_INCONSISTENT, STATUS_INCOMPLETE)

LEG_PRINCIPAL = "principal"
LEG_INTEREST = "interest"

_COMPOUNDED = "COMPOUNDED"
_PAYOUT_PENDING = "PENDING"
_PAYOUT_CONFIRMED = "CONFIRMED"
_DISCREPANCY_OPEN = "OPEN"
_CREDIT = "CREDIT"
_COMPLETED_TERM_STATUSES = frozenset({"MATURED_SETTLED", "CLOSED"})


@dataclass(frozen=True)
class TermRef:
    id: int
    deposit_account_number: str
    institution_name: str
    status: str
    principal_amount: Decimal
    currency: str
    interest_payout_frequency: str
    portfolio_id: int | None = None
    bank_account_id: int | None = None
    renewal_of_id: int | None = None


@dataclass(frozen=True)
class LedgerMovement:
    """Bank movement linked to the completed term (maturity/closure legs)."""

    id: int
    leg: str
    direction: str
    amount: Decimal
    currency: str
    movement_date: date
    linked_fixed_deposit_id: int | None


@dataclass(frozen=True)
class SettlementRecord:
    id: int
    fixed_deposit_id: int
    settlement_date: date
    principal_returned: Decimal
    gross_interest: Decimal
    tax_withheld: Decimal
    net_interest: Decimal
    total_net_proceeds: Decimal
    principal_movement_id: int | None
    interest_movement_id: int | None


@dataclass(frozen=True)
class PendingPayoutRecord:
    id: int
    status: str
    suggested_net_interest: Decimal | None
    net_interest: Decimal | None
    payment_date: date | None
    movement_id: int | None
    discrepancy_status: str
    discrepancy_amount: Decimal | None


@dataclass(frozen=True)
class RenewalAuditInput:
    renewal_id: int
    renewal_date: date
    currency: str
    old_principal: Decimal
    direct_reinvest_amount: Decimal
    cash_payout_amount: Decimal
    gross_interest: Decimal
    tax_withheld: Decimal
    net_interest: Decimal
    total_maturity_value: Decimal
    old_term: TermRef
    new_term: TermRef
    settlement: SettlementRecord | None
    movements: tuple[LedgerMovement, ...] = ()
    pending_payout: PendingPayoutRecord | None = None


@dataclass(frozen=True)
class AuditFinding:
    code: str
    kind: str
    message: str


@dataclass(frozen=True)
class RenewalAuditTotals:
    old_principal: Decimal
    gross_interest: Decimal
    tax_withheld: Decimal
    net_interest: Decimal
    total_available: Decimal
    reinvested_principal: Decimal
    cash_payout_recorded: Decimal
    allocation_gap: Decimal
    expected_interest_cash: Decimal | None
    expected_principal_cash: Decimal | None
    reinvested_interest: Decimal | None
    ledger_payout_total: Decimal
    ledger_interest_total: Decimal
    ledger_principal_total: Decimal
    unlinked_movement_total: Decimal
    pending_estimate_net: Decimal
    confirmed_later_payout_net: Decimal


@dataclass(frozen=True)
class RenewalAuditResult:
    renewal_id: int
    renewal_date: date
    currency: str
    status: str
    findings: tuple[AuditFinding, ...]
    totals: RenewalAuditTotals
    old_term: TermRef
    new_term: TermRef
    settlement_id: int | None
    settlement_movement_ids: tuple[int, ...]
    unlinked_movement_ids: tuple[int, ...]
    pending_payout_id: int | None


@dataclass(frozen=True)
class CurrencyAuditTotals:
    currency: str
    renewal_count: int
    old_principal: Decimal
    net_interest: Decimal
    reinvested_principal: Decimal
    cash_payout_recorded: Decimal
    ledger_payout_total: Decimal
    unlinked_movement_total: Decimal
    pending_estimate_net: Decimal
    confirmed_later_payout_net: Decimal


@dataclass(frozen=True)
class RenewalAuditSummary:
    renewal_count: int
    status_counts: dict[str, int]
    finding_counts: dict[str, int]
    totals_by_currency: tuple[CurrencyAuditTotals, ...] = field(default_factory=tuple)


def _fmt(amount: Decimal | None, currency: str) -> str:
    if amount is None:
        return "n/a"
    return f"{currency} {amount:,.2f}"


class _Findings:
    def __init__(self, currency: str):
        self.currency = currency
        self.items: list[AuditFinding] = []

    def inconsistent(self, code: str, message: str) -> None:
        self.items.append(AuditFinding(code=code, kind=STATUS_INCONSISTENT, message=message))

    def incomplete(self, code: str, message: str) -> None:
        self.items.append(AuditFinding(code=code, kind=STATUS_INCOMPLETE, message=message))

    def money(self, amount: Decimal | None) -> str:
        return _fmt(amount, self.currency)


def _signed(movement: LedgerMovement) -> Decimal:
    return movement.amount if movement.direction == _CREDIT else -movement.amount


def _check_terms(audit: RenewalAuditInput, f: _Findings) -> None:
    old, new = audit.old_term, audit.new_term
    if audit.old_principal != old.principal_amount:
        f.inconsistent(
            "OLD_PRINCIPAL_MISMATCH",
            f"Renewal records old principal {f.money(audit.old_principal)} but term "
            f"{old.deposit_account_number} has principal {f.money(old.principal_amount)}.",
        )
    if audit.direct_reinvest_amount != new.principal_amount:
        f.inconsistent(
            "REINVESTED_PRINCIPAL_MISMATCH",
            f"Renewal records reinvested principal {f.money(audit.direct_reinvest_amount)} "
            f"but successor term {new.deposit_account_number} has principal "
            f"{f.money(new.principal_amount)}.",
        )
    if new.renewal_of_id != old.id:
        f.inconsistent(
            "TERM_LINK_MISMATCH",
            f"Successor term {new.deposit_account_number} is not linked back to "
            f"term {old.deposit_account_number} (renewal_of={new.renewal_of_id}).",
        )
    if old.status not in _COMPLETED_TERM_STATUSES:
        f.inconsistent(
            "TERM_STATUS_MISMATCH",
            f"Renewed term {old.deposit_account_number} has status {old.status}; "
            "a renewed predecessor should be completed (MATURED_SETTLED or CLOSED).",
        )
    mismatched = sorted(
        {c for c in (old.currency, new.currency) if c and c != audit.currency}
    )
    if mismatched:
        f.inconsistent(
            "CURRENCY_MISMATCH",
            f"Renewal currency {audit.currency} differs from term currency "
            f"{', '.join(mismatched)}.",
        )


def _check_interest(audit: RenewalAuditInput, f: _Findings) -> None:
    if (
        audit.tax_withheld > audit.gross_interest
        or audit.gross_interest - audit.tax_withheld != audit.net_interest
    ):
        f.inconsistent(
            "INTEREST_BREAKDOWN_MISMATCH",
            f"Gross interest {f.money(audit.gross_interest)} minus tax withheld "
            f"{f.money(audit.tax_withheld)} does not equal net interest "
            f"{f.money(audit.net_interest)}.",
        )
    expected_total = audit.old_principal + audit.net_interest
    if audit.total_maturity_value != expected_total:
        f.inconsistent(
            "MATURITY_TOTAL_MISMATCH",
            f"Recorded maturity total {f.money(audit.total_maturity_value)} differs from "
            f"old principal + net interest {f.money(expected_total)}.",
        )


def _check_allocation(audit: RenewalAuditInput, f: _Findings):
    available = audit.old_principal + audit.net_interest
    allocated = audit.direct_reinvest_amount + audit.cash_payout_amount
    try:
        return allocate_renewal_proceeds(
            old_principal=audit.old_principal,
            net_interest=audit.net_interest,
            new_principal=audit.direct_reinvest_amount,
            cash_payout_amount=audit.cash_payout_amount,
        )
    except ValueError:
        pass
    message = (
        f"Old principal {f.money(audit.old_principal)} + final net interest "
        f"{f.money(audit.net_interest)} = {f.money(available)}, but reinvested principal "
        f"{f.money(audit.direct_reinvest_amount)} + cash payout "
        f"{f.money(audit.cash_payout_amount)} = {f.money(allocated)} "
        f"(gap {f.money(available - allocated)})."
    )
    pending = audit.pending_payout
    if (
        pending is not None
        and pending.suggested_net_interest
        and allocated - available == pending.suggested_net_interest
    ):
        message += (
            " The gap equals the pending interest estimate, which is not settled proceeds."
        )
    f.inconsistent("ALLOCATION_MISMATCH", message)
    return None


def _check_settlement(audit: RenewalAuditInput, f: _Findings) -> None:
    s = audit.settlement
    if s is None:
        f.incomplete(
            "MISSING_SETTLEMENT",
            f"No settlement is recorded for renewed term {audit.old_term.deposit_account_number}.",
        )
        return
    diffs = []
    if s.fixed_deposit_id != audit.old_term.id:
        diffs.append(f"settles term id {s.fixed_deposit_id}, not {audit.old_term.id}")
    for label, settled, renewed in (
        ("principal returned", s.principal_returned, audit.old_principal),
        ("gross interest", s.gross_interest, audit.gross_interest),
        ("tax withheld", s.tax_withheld, audit.tax_withheld),
        ("net interest", s.net_interest, audit.net_interest),
        ("total net proceeds", s.total_net_proceeds, audit.total_maturity_value),
    ):
        if settled != renewed:
            diffs.append(f"{label} {f.money(settled)} vs renewal {f.money(renewed)}")
    if diffs:
        f.inconsistent(
            "SETTLEMENT_MISMATCH",
            f"Settlement #{s.id} disagrees with the renewal: {'; '.join(diffs)}.",
        )


def _check_pending(audit: RenewalAuditInput, f: _Findings) -> None:
    pending = audit.pending_payout
    if pending is None:
        if (
            audit.old_term.interest_payout_frequency == _COMPOUNDED
            and audit.gross_interest == 0
            and audit.net_interest == 0
        ):
            f.incomplete(
                "NO_FINAL_INTEREST_RECORDED",
                f"Cumulative term {audit.old_term.deposit_account_number} was renewed with "
                "no final interest and no pending payout; compare with the bank statement.",
            )
        return

    if audit.net_interest > 0:
        f.inconsistent(
            "FINAL_INTEREST_DOUBLE_RECORDED",
            f"Renewal records final net interest {f.money(audit.net_interest)} and the term "
            f"also has a {pending.status.lower()} maturity payout #{pending.id}; final "
            "interest must be recorded once.",
        )

    if pending.status == _PAYOUT_PENDING:
        f.incomplete(
            "FINAL_INTEREST_PENDING",
            f"Final interest is awaiting bank confirmation (pending payout #{pending.id}, "
            f"estimated net {f.money(pending.suggested_net_interest)}); the estimate is not "
            "counted as settled proceeds.",
        )
        return

    net = pending.net_interest or _ZERO
    if pending.movement_id is None and net > 0:
        f.incomplete(
            "CONFIRMED_PAYOUT_MOVEMENT_MISSING",
            f"Confirmed payout #{pending.id} records net {f.money(net)} but has no linked "
            "bank credit.",
        )
    if pending.discrepancy_status == _DISCREPANCY_OPEN:
        f.incomplete(
            "PAYOUT_DISCREPANCY_OPEN",
            f"Confirmed payout #{pending.id} differs from its estimate by "
            f"{f.money(pending.discrepancy_amount)} and has not been reviewed.",
        )


def _check_ledger(
    audit: RenewalAuditInput,
    f: _Findings,
    *,
    allocation,
    settlement_movements: list[LedgerMovement],
    payout_movement: LedgerMovement | None,
    unlinked: list[LedgerMovement],
) -> None:
    for movement in settlement_movements + ([payout_movement] if payout_movement else []):
        problems = []
        if movement.direction != _CREDIT:
            problems.append(f"direction {movement.direction}")
        if movement.currency != audit.currency:
            problems.append(f"currency {movement.currency}")
        if movement.linked_fixed_deposit_id != audit.old_term.id:
            problems.append(f"linked to term id {movement.linked_fixed_deposit_id}")
        if problems:
            f.inconsistent(
                "LEDGER_LINK_MISMATCH",
                f"Bank movement #{movement.id} referenced by this renewal has "
                f"{', '.join(problems)}.",
            )

    ledger_total = sum((_signed(m) for m in settlement_movements), _ZERO)
    payout = audit.cash_payout_amount
    if ledger_total != payout:
        if not settlement_movements and payout > 0:
            f.incomplete(
                "MISSING_PAYOUT_MOVEMENTS",
                f"Renewal records a cash payout of {f.money(payout)} but no bank credit is "
                "linked to the settlement.",
            )
        else:
            f.inconsistent(
                "LEDGER_PAYOUT_MISMATCH",
                f"Linked bank credits total {f.money(ledger_total)} but the recorded cash "
                f"payout is {f.money(payout)} (difference {f.money(ledger_total - payout)}).",
            )
    elif allocation is not None and settlement_movements:
        interest = sum((_signed(m) for m in settlement_movements if m.leg == LEG_INTEREST), _ZERO)
        principal = ledger_total - interest
        if (
            interest != allocation.interest_cash_amount
            or principal != allocation.principal_cash_amount
        ):
            f.inconsistent(
                "LEDGER_SPLIT_MISMATCH",
                f"Bank credits split interest {f.money(interest)} / principal "
                f"{f.money(principal)}, but the renewal rules attribute interest "
                f"{f.money(allocation.interest_cash_amount)} / principal "
                f"{f.money(allocation.principal_cash_amount)}.",
            )

    pending = audit.pending_payout
    if payout_movement is not None and pending is not None:
        net = pending.net_interest or _ZERO
        if _signed(payout_movement) != net:
            f.inconsistent(
                "CONFIRMED_PAYOUT_LEDGER_MISMATCH",
                f"Confirmed payout #{pending.id} records net {f.money(net)} but its bank "
                f"credit #{payout_movement.id} is {f.money(payout_movement.amount)}.",
            )

    if unlinked:
        ids = ", ".join(f"#{m.id}" for m in unlinked)
        total = sum((_signed(m) for m in unlinked), _ZERO)
        f.incomplete(
            "UNLINKED_MATURITY_MOVEMENT",
            f"Maturity bank movement(s) {ids} totalling {f.money(total)} are linked to term "
            f"{audit.old_term.deposit_account_number} but not to its settlement or payout; "
            "cannot tell whether they belong to this renewal.",
        )


def audit_renewal(audit: RenewalAuditInput) -> RenewalAuditResult:
    """Classify one recorded renewal; never mutates inputs."""
    f = _Findings(audit.currency)
    settlement = audit.settlement
    pending = audit.pending_payout

    settlement_ids = set()
    if settlement is not None:
        settlement_ids = {
            mid
            for mid in (settlement.principal_movement_id, settlement.interest_movement_id)
            if mid is not None
        }
    payout_movement_id = pending.movement_id if pending is not None else None

    settlement_movements: list[LedgerMovement] = []
    payout_movement: LedgerMovement | None = None
    unlinked: list[LedgerMovement] = []
    for movement in sorted(audit.movements, key=lambda m: m.id):
        if movement.id in settlement_ids:
            settlement_movements.append(movement)
        elif movement.id == payout_movement_id:
            payout_movement = movement
        else:
            unlinked.append(movement)

    _check_terms(audit, f)
    _check_interest(audit, f)
    allocation = _check_allocation(audit, f)
    _check_settlement(audit, f)
    _check_pending(audit, f)
    _check_ledger(
        audit,
        f,
        allocation=allocation,
        settlement_movements=settlement_movements,
        payout_movement=payout_movement,
        unlinked=unlinked,
    )

    kinds = {finding.kind for finding in f.items}
    if STATUS_INCONSISTENT in kinds:
        status = STATUS_INCONSISTENT
    elif STATUS_INCOMPLETE in kinds:
        status = STATUS_INCOMPLETE
    else:
        status = STATUS_CONSISTENT

    ledger_total = sum((_signed(m) for m in settlement_movements), _ZERO)
    ledger_interest = sum(
        (_signed(m) for m in settlement_movements if m.leg == LEG_INTEREST), _ZERO
    )
    available = audit.old_principal + audit.net_interest
    pending_estimate = _ZERO
    confirmed_net = _ZERO
    if pending is not None:
        if pending.status == _PAYOUT_PENDING:
            pending_estimate = pending.suggested_net_interest or _ZERO
        elif pending.status == _PAYOUT_CONFIRMED:
            confirmed_net = pending.net_interest or _ZERO

    totals = RenewalAuditTotals(
        old_principal=audit.old_principal,
        gross_interest=audit.gross_interest,
        tax_withheld=audit.tax_withheld,
        net_interest=audit.net_interest,
        total_available=available,
        reinvested_principal=audit.direct_reinvest_amount,
        cash_payout_recorded=audit.cash_payout_amount,
        allocation_gap=available - (audit.direct_reinvest_amount + audit.cash_payout_amount),
        expected_interest_cash=allocation.interest_cash_amount if allocation else None,
        expected_principal_cash=allocation.principal_cash_amount if allocation else None,
        reinvested_interest=allocation.reinvested_interest_amount if allocation else None,
        ledger_payout_total=ledger_total,
        ledger_interest_total=ledger_interest,
        ledger_principal_total=ledger_total - ledger_interest,
        unlinked_movement_total=sum((_signed(m) for m in unlinked), _ZERO),
        pending_estimate_net=pending_estimate,
        confirmed_later_payout_net=confirmed_net,
    )
    return RenewalAuditResult(
        renewal_id=audit.renewal_id,
        renewal_date=audit.renewal_date,
        currency=audit.currency,
        status=status,
        findings=tuple(f.items),
        totals=totals,
        old_term=audit.old_term,
        new_term=audit.new_term,
        settlement_id=settlement.id if settlement is not None else None,
        settlement_movement_ids=tuple(m.id for m in settlement_movements),
        unlinked_movement_ids=tuple(m.id for m in unlinked),
        pending_payout_id=pending.id if pending is not None else None,
    )


def summarize_renewal_audit(results: list[RenewalAuditResult]) -> RenewalAuditSummary:
    """Status/finding counts and native-currency totals (never mixed across currencies)."""
    status_counts = {status: 0 for status in AUDIT_STATUSES}
    finding_counts: Counter[str] = Counter()
    by_currency: dict[str, dict] = {}
    for result in results:
        status_counts[result.status] += 1
        finding_counts.update(finding.code for finding in result.findings)
        bucket = by_currency.setdefault(
            result.currency,
            {
                "renewal_count": 0,
                "old_principal": _ZERO,
                "net_interest": _ZERO,
                "reinvested_principal": _ZERO,
                "cash_payout_recorded": _ZERO,
                "ledger_payout_total": _ZERO,
                "unlinked_movement_total": _ZERO,
                "pending_estimate_net": _ZERO,
                "confirmed_later_payout_net": _ZERO,
            },
        )
        bucket["renewal_count"] += 1
        for key in bucket:
            if key != "renewal_count":
                bucket[key] += getattr(result.totals, key)
    return RenewalAuditSummary(
        renewal_count=len(results),
        status_counts=status_counts,
        finding_counts=dict(sorted(finding_counts.items())),
        totals_by_currency=tuple(
            CurrencyAuditTotals(currency=currency, **values)
            for currency, values in sorted(by_currency.items())
        ),
    )
