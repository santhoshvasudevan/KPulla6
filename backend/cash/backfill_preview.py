"""Legacy cash backfill preview simulation (Cash-7A — read-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist

from cash.models import CashEntryType, CashLedgerEntry
from cash.services import list_ledger_points_for_portfolio
from finance.cash import (
    CashLedgerPoint,
    cash_balance_on_date,
    mf_buy_cash_required,
    mf_sell_cash_proceeds,
    stock_buy_cash_required,
    stock_sell_cash_proceeds,
)
from portfolios import dates as portfolio_dates
from portfolios.models import Portfolio
from portfolios.summary_service import fifo_eligible_queryset
from transactions.models import Transaction, TransactionType

_BACKFILL_SOURCE = "Backfill deposit"
_ZERO = Decimal("0")
_SETTLEMENT_TYPES = frozenset(
    {CashEntryType.BUY_SETTLEMENT, CashEntryType.SELL_SETTLEMENT}
)


class BackfillPreviewValidationError(Exception):
    pass


@dataclass
class BackfillShortfallRow:
    date: date
    currency: str
    required: Decimal
    available_before: Decimal
    shortfall: Decimal
    reason: str


@dataclass
class BackfillProposedDeposit:
    portfolio_id: int
    date: date
    currency: str
    amount: Decimal
    source_of_funds: str = _BACKFILL_SOURCE
    note: str = ""


@dataclass
class BackfillPreviewSummary:
    transaction_count: int = 0
    existing_cash_entry_count: int = 0
    proposed_deposit_count: int = 0
    total_proposed_by_currency: list[tuple[str, Decimal]] = field(default_factory=list)


@dataclass
class BackfillPreviewResult:
    portfolio: Portfolio
    start_date: date
    end_date: date
    mode: str
    can_enable_cash_aware_after_apply: bool
    summary: BackfillPreviewSummary
    proposed_deposits: list[BackfillProposedDeposit] = field(default_factory=list)
    shortfalls: list[BackfillShortfallRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    row_errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class _SimEvent:
    sort_date: date
    order: int
    currency: str
    txn_type: str
    reason: str
    quantity: Decimal | None = None
    price_per_share: Decimal | None = None
    fees: Decimal | None = None
    paid_value: Decimal | None = None
    units_allotted: Decimal | None = None
    nav: Decimal | None = None
    txn_id: int | None = None
    skip_cash_effect: bool = False


def resolve_backfill_date_range(
    portfolio: Portfolio,
    *,
    start_date: date | None,
    end_date: date | None,
    today: date | None = None,
) -> tuple[date, date]:
    today = today or portfolio_dates.current_date()
    effective_end = end_date or today
    if start_date is not None:
        effective_start = start_date
    else:
        earliest_txn = (
            Transaction.objects.filter(portfolio=portfolio)
            .order_by("date")
            .values_list("date", flat=True)
            .first()
        )
        earliest_cash = (
            CashLedgerEntry.objects.filter(portfolio=portfolio)
            .order_by("date")
            .values_list("date", flat=True)
            .first()
        )
        candidates = [d for d in (earliest_txn, earliest_cash) if d is not None]
        effective_start = min(candidates) if candidates else effective_end
    if effective_start > effective_end:
        raise BackfillPreviewValidationError("start_date must be on or before end_date")
    return effective_start, effective_end


def _transaction_ids_with_settlements(portfolio_id: int) -> set[int]:
    return set(
        CashLedgerEntry.objects.filter(
            portfolio_id=portfolio_id,
            linked_transaction_id__isnull=False,
            entry_type__in=_SETTLEMENT_TYPES,
        ).values_list("linked_transaction_id", flat=True)
    )


def _is_mutual_fund_transaction(txn: Transaction) -> bool:
    try:
        txn.mutual_fund_detail
    except ObjectDoesNotExist:
        return False
    return True


def _txn_to_event(txn: Transaction, *, skip_cash_effect: bool) -> _SimEvent | None:
    currency = (txn.currency or "EUR").strip().upper()
    symbol = txn.asset_symbol
    reason = f"{txn.type} {symbol}"

    if _is_mutual_fund_transaction(txn):
        detail = txn.mutual_fund_detail
        ledger_date = detail.investment_date
        return _SimEvent(
            sort_date=ledger_date,
            order=txn.id,
            currency=currency,
            txn_type=txn.type,
            reason=reason,
            paid_value=detail.paid_value,
            units_allotted=detail.units_allotted,
            nav=detail.nav,
            fees=txn.fees or _ZERO,
            txn_id=txn.id,
            skip_cash_effect=skip_cash_effect,
        )

    if txn.type in {TransactionType.STOCK_SPLIT, TransactionType.DIVIDEND}:
        return _SimEvent(
            sort_date=txn.date,
            order=txn.id,
            currency=currency,
            txn_type=txn.type,
            reason=reason,
            txn_id=txn.id,
            skip_cash_effect=True,
        )

    return _SimEvent(
        sort_date=txn.date,
        order=txn.id,
        currency=currency,
        txn_type=txn.type,
        reason=reason,
        quantity=txn.quantity,
        price_per_share=txn.price_per_share,
        fees=txn.fees or _ZERO,
        txn_id=txn.id,
        skip_cash_effect=skip_cash_effect,
    )


def _cash_effect(event: _SimEvent) -> tuple[Decimal | None, bool]:
    """Return (signed ledger amount, is_buy) or (None, False)."""
    if event.skip_cash_effect:
        return None, False

    if event.txn_type in {TransactionType.STOCK_SPLIT, TransactionType.DIVIDEND}:
        return None, False

    if event.txn_type == TransactionType.BUY:
        if event.paid_value is not None:
            required = mf_buy_cash_required(event.paid_value)
        else:
            required = stock_buy_cash_required(
                event.quantity or _ZERO,
                event.price_per_share or _ZERO,
                event.fees or _ZERO,
            )
        return -required, True

    if event.txn_type == TransactionType.SELL:
        if event.paid_value is not None:
            proceeds = mf_sell_cash_proceeds(
                paid_value=event.paid_value,
                units_allotted=event.units_allotted or _ZERO,
                nav=event.nav or _ZERO,
                fees=event.fees or _ZERO,
            )
        else:
            proceeds = stock_sell_cash_proceeds(
                event.quantity or _ZERO,
                event.price_per_share or _ZERO,
                event.fees or _ZERO,
            )
        if proceeds <= 0:
            return None, False
        return proceeds, False

    return None, False


def _deposit_note(reason: str) -> str:
    return f"Proposed before historical {reason}"


def _merge_proposed_deposits(
    deposits: list[BackfillProposedDeposit],
    *,
    portfolio_id: int,
) -> list[BackfillProposedDeposit]:
    merged_amount: dict[tuple[date, str], Decimal] = {}
    notes_by_key: dict[tuple[date, str], list[str]] = {}
    for dep in deposits:
        key = (dep.date, dep.currency)
        merged_amount[key] = merged_amount.get(key, _ZERO) + dep.amount
        notes_by_key.setdefault(key, []).append(dep.note)
    out: list[BackfillProposedDeposit] = []
    for (d, ccy), amt in sorted(merged_amount.items()):
        unique_notes = list(dict.fromkeys(notes_by_key.get((d, ccy), [])))
        note = unique_notes[0] if len(unique_notes) == 1 else "; ".join(unique_notes)
        out.append(
            BackfillProposedDeposit(
                portfolio_id=portfolio_id,
                date=d,
                currency=ccy,
                amount=amt,
                source_of_funds=_BACKFILL_SOURCE,
                note=note,
            )
        )
    return out


def simulate_cash_backfill_preview(
    portfolio: Portfolio,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    mode: str = "shortfall",
    today: date | None = None,
) -> BackfillPreviewResult:
    """
    Read-only simulation: propose same-currency CASH_DEPOSIT rows before BUY shortfalls.

    Uses existing ledger rows (including linked settlements). Skips cash effects for
    transactions that already have settlement rows to avoid double-counting.
    """
    if mode != "shortfall":
        raise BackfillPreviewValidationError(f"Unsupported mode: {mode!r}")

    effective_start, effective_end = resolve_backfill_date_range(
        portfolio, start_date=start_date, end_date=end_date, today=today
    )
    warnings: list[str] = []
    if portfolio.cash_aware_enabled:
        warnings.append(
            "Portfolio is already cash-aware; preview is informational only."
        )

    existing_entry_count = CashLedgerEntry.objects.filter(portfolio=portfolio).count()
    simulated: list[CashLedgerPoint] = list_ledger_points_for_portfolio(portfolio)
    settled_txn_ids = _transaction_ids_with_settlements(portfolio.id)

    queryset = fifo_eligible_queryset([portfolio.id])
    txns: list[Transaction] = []
    for txn in queryset:
        if _is_mutual_fund_transaction(txn):
            if txn.mutual_fund_detail.investment_date > effective_end:
                continue
        elif txn.date > effective_end:
            continue
        txns.append(txn)
    events: list[_SimEvent] = []
    for txn in txns:
        event = _txn_to_event(
            txn, skip_cash_effect=txn.id in settled_txn_ids
        )
        if event is not None:
            events.append(event)
    events.sort(key=lambda e: (e.sort_date, e.order))

    shortfalls: list[BackfillShortfallRow] = []
    raw_deposits: list[BackfillProposedDeposit] = []

    for event in events:
        amount, is_buy = _cash_effect(event)
        if amount is None:
            continue

        if is_buy:
            required = abs(amount)
            available = cash_balance_on_date(simulated, event.sort_date).get(
                event.currency, _ZERO
            )
            if available < required:
                gap = required - available
                if effective_start <= event.sort_date <= effective_end:
                    shortfalls.append(
                        BackfillShortfallRow(
                            date=event.sort_date,
                            currency=event.currency,
                            required=required,
                            available_before=available,
                            shortfall=gap,
                            reason=event.reason,
                        )
                    )
                    raw_deposits.append(
                        BackfillProposedDeposit(
                            portfolio_id=portfolio.id,
                            date=event.sort_date,
                            currency=event.currency,
                            amount=gap,
                            note=_deposit_note(event.reason),
                        )
                    )
                simulated.append(
                    CashLedgerPoint(
                        date=event.sort_date,
                        currency=event.currency,
                        amount=gap,
                    )
                )
            simulated.append(
                CashLedgerPoint(
                    date=event.sort_date,
                    currency=event.currency,
                    amount=amount,
                )
            )
        else:
            simulated.append(
                CashLedgerPoint(
                    date=event.sort_date,
                    currency=event.currency,
                    amount=amount,
                )
            )

    proposed = _merge_proposed_deposits(raw_deposits, portfolio_id=portfolio.id)
    totals: dict[str, Decimal] = {}
    for dep in proposed:
        totals[dep.currency] = totals.get(dep.currency, _ZERO) + dep.amount

    return BackfillPreviewResult(
        portfolio=portfolio,
        start_date=effective_start,
        end_date=effective_end,
        mode=mode,
        can_enable_cash_aware_after_apply=len(proposed) == 0,
        summary=BackfillPreviewSummary(
            transaction_count=len(txns),
            existing_cash_entry_count=existing_entry_count,
            proposed_deposit_count=len(proposed),
            total_proposed_by_currency=sorted(totals.items()),
        ),
        proposed_deposits=proposed,
        shortfalls=shortfalls,
        warnings=warnings,
    )


def backfill_preview_to_response_dict(result: BackfillPreviewResult) -> dict[str, Any]:
    p = result.portfolio
    return {
        "portfolio_id": p.id,
        "portfolio_name": p.name,
        "cash_aware_enabled": p.cash_aware_enabled,
        "start_date": result.start_date.isoformat(),
        "end_date": result.end_date.isoformat(),
        "mode": result.mode,
        "can_enable_cash_aware_after_apply": result.can_enable_cash_aware_after_apply,
        "summary": {
            "transaction_count": result.summary.transaction_count,
            "existing_cash_entry_count": result.summary.existing_cash_entry_count,
            "proposed_deposit_count": result.summary.proposed_deposit_count,
            "total_proposed_by_currency": [
                {"currency": ccy, "amount": float(amt)}
                for ccy, amt in result.summary.total_proposed_by_currency
            ],
        },
        "proposed_deposits": [
            {
                "portfolio_id": d.portfolio_id,
                "date": d.date.isoformat(),
                "currency": d.currency,
                "amount": float(d.amount),
                "source_of_funds": d.source_of_funds,
                "note": d.note,
            }
            for d in result.proposed_deposits
        ],
        "shortfalls": [
            {
                "date": s.date.isoformat(),
                "currency": s.currency,
                "required": float(s.required),
                "available_before": float(s.available_before),
                "shortfall": float(s.shortfall),
                "reason": s.reason,
            }
            for s in result.shortfalls
        ],
        "warnings": result.warnings,
    }
