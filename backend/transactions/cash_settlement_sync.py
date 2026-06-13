"""Backfill missing BUY/SELL settlement rows for cash-aware portfolios (CASH-HIST-1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction as db_transaction

from cash.models import CashEntryType, CashLedgerEntry
from cash.services import ledger_entries_queryset, ledger_entry_to_point
from finance.cash import CashLedgerPoint, cash_balance_timeseries
from portfolios.models import Portfolio
from transactions.cash_settlement import (
    SettlementSpec,
    _get_linked_settlement,
    _mf_settlement_spec,
    _stock_settlement_spec,
)
from transactions.models import MutualFundTransactionDetail, Transaction, TransactionType


class CashSettlementSyncError(Exception):
    """Base error for settlement sync operations."""


class CashSettlementSyncBlockedError(CashSettlementSyncError):
    """Apply blocked — would cause negative historical cash balance."""

    def __init__(self, impacts: list[dict[str, Any]]) -> None:
        super().__init__("Settlement sync would make historical cash balance negative.")
        self.impacts = impacts


@dataclass(frozen=True)
class PlannedSettlement:
    transaction_id: int
    asset_symbol: str
    transaction_type: str
    entry_type: str
    amount: Decimal
    ledger_date: date
    currency: str


@dataclass(frozen=True)
class SettlementMismatch:
    transaction_id: int
    settlement_id: int
    code: str
    detail: str


@dataclass
class SettlementSyncPlan:
    portfolio_id: int
    portfolio_name: str
    cash_aware_enabled: bool
    to_create: list[PlannedSettlement] = field(default_factory=list)
    mismatches: list[SettlementMismatch] = field(default_factory=list)
    already_synced: int = 0
    skipped_non_settlement: int = 0

    @property
    def create_count(self) -> int:
        return len(self.to_create)


def _expected_spec(txn: Transaction) -> SettlementSpec:
    try:
        detail = txn.mutual_fund_detail
    except MutualFundTransactionDetail.DoesNotExist:
        detail = None
    if detail is not None:
        return _mf_settlement_spec(txn, detail)
    return _stock_settlement_spec(txn)


def _compare_settlement(
    txn: Transaction,
    existing: CashLedgerEntry,
    spec: SettlementSpec,
) -> list[SettlementMismatch]:
    mismatches: list[SettlementMismatch] = []
    if spec.entry_type is None:
        return mismatches
    assert spec.amount is not None
    assert spec.ledger_date is not None
    assert spec.currency is not None

    checks = (
        ("settlement_type_mismatch", existing.entry_type, spec.entry_type),
        ("settlement_amount_mismatch", existing.amount, spec.amount),
        ("settlement_date_mismatch", existing.date, spec.ledger_date),
        ("settlement_currency_mismatch", existing.currency, spec.currency),
    )
    for code, actual, expected in checks:
        if actual != expected:
            mismatches.append(
                SettlementMismatch(
                    transaction_id=txn.id,
                    settlement_id=existing.id,
                    code=code,
                    detail=f"expected {expected!r}, got {actual!r}",
                )
            )
    return mismatches


def plan_cash_settlement_sync(portfolio: Portfolio) -> SettlementSyncPlan:
    """Identify missing or mismatched settlement rows for one portfolio."""
    plan = SettlementSyncPlan(
        portfolio_id=portfolio.id,
        portfolio_name=portfolio.name,
        cash_aware_enabled=portfolio.cash_aware_enabled,
    )
    txns = (
        Transaction.objects.filter(portfolio_id=portfolio.id)
        .select_related("mutual_fund_detail")
        .order_by("date", "id")
    )
    for txn in txns:
        if txn.type in {TransactionType.STOCK_SPLIT, TransactionType.DIVIDEND}:
            plan.skipped_non_settlement += 1
            continue

        if txn.type not in {TransactionType.BUY, TransactionType.SELL}:
            continue

        spec = _expected_spec(txn)
        if spec.entry_type is None:
            plan.skipped_non_settlement += 1
            continue

        existing = _get_linked_settlement(txn)
        if existing is None:
            assert spec.amount is not None
            assert spec.ledger_date is not None
            assert spec.currency is not None
            plan.to_create.append(
                PlannedSettlement(
                    transaction_id=txn.id,
                    asset_symbol=txn.asset_symbol,
                    transaction_type=txn.type,
                    entry_type=spec.entry_type,
                    amount=spec.amount,
                    ledger_date=spec.ledger_date,
                    currency=spec.currency,
                )
            )
            continue

        plan.already_synced += 1
        plan.mismatches.extend(_compare_settlement(txn, existing, spec))

    plan.to_create.sort(key=lambda p: (p.ledger_date, p.transaction_id))
    return plan


def _points_with_planned(
    portfolio: Portfolio,
    planned: list[PlannedSettlement],
) -> dict[str, list[CashLedgerPoint]]:
    by_currency: dict[str, list[CashLedgerPoint]] = {}
    for row in ledger_entries_queryset(portfolio):
        by_currency.setdefault(row.currency, []).append(ledger_entry_to_point(row))
    for item in planned:
        by_currency.setdefault(item.currency, []).append(
            CashLedgerPoint(
                date=item.ledger_date,
                currency=item.currency,
                amount=item.amount,
            )
        )
    return by_currency


def validate_plan_negative_cash(
    portfolio: Portfolio,
    plan: SettlementSyncPlan,
) -> list[dict[str, Any]]:
    """Return negative-balance impacts if applying ``plan`` would breach zero cash."""
    if not plan.to_create:
        return []

    points_by_ccy = _points_with_planned(portfolio, plan.to_create)
    impacts: list[dict[str, Any]] = []

    for currency, points in sorted(points_by_ccy.items()):
        if not points:
            continue
        dates = [p.date for p in points]
        start = min(dates)
        end = max(dates)
        series = cash_balance_timeseries(points, start, end).get(currency, [])
        earliest_negative: date | None = None
        lowest = Decimal("0")
        for day, balance in series:
            if balance < lowest:
                lowest = balance
            if balance < 0 and earliest_negative is None:
                earliest_negative = day

        if earliest_negative is None:
            continue

        trigger_txn_ids = [
            p.transaction_id
            for p in plan.to_create
            if p.currency == currency and p.ledger_date == earliest_negative
        ]
        impacts.append(
            {
                "currency": currency,
                "earliest_negative_date": earliest_negative.isoformat(),
                "lowest_balance": str(lowest),
                "transactions_causing_shortfall": trigger_txn_ids,
                "recommendation": (
                    "Add historical cash deposits (manual or Bulk Cash Entries) "
                    "before the earliest negative date, then re-run sync."
                ),
            }
        )

    return impacts


def plan_to_dict(plan: SettlementSyncPlan) -> dict[str, Any]:
    return {
        "portfolio_id": plan.portfolio_id,
        "portfolio_name": plan.portfolio_name,
        "cash_aware_enabled": plan.cash_aware_enabled,
        "create_count": plan.create_count,
        "already_synced": plan.already_synced,
        "skipped_non_settlement": plan.skipped_non_settlement,
        "mismatch_count": len(plan.mismatches),
        "to_create": [asdict(p) for p in plan.to_create],
        "mismatches": [asdict(m) for m in plan.mismatches],
    }


@db_transaction.atomic
def apply_cash_settlement_sync(portfolio: Portfolio) -> dict[str, Any]:
    """
    Create missing settlement rows for ``portfolio``.

    Idempotent: second call creates zero rows. Raises when mismatches exist or
    apply would drive historical cash negative.
    """
    portfolio = Portfolio.objects.select_for_update().get(pk=portfolio.pk)
    plan = plan_cash_settlement_sync(portfolio)

    if plan.mismatches:
        raise CashSettlementSyncError(
            f"Cannot apply: {len(plan.mismatches)} settlement mismatch(es) — "
            "fix manually or add an explicit repair flag in a future phase."
        )

    impacts = validate_plan_negative_cash(portfolio, plan)
    if impacts:
        raise CashSettlementSyncBlockedError(impacts)

    created = 0
    for item in plan.to_create:
        if _get_linked_settlement(
            Transaction.objects.get(pk=item.transaction_id)
        ) is not None:
            continue
        entry = CashLedgerEntry(
            portfolio=portfolio,
            date=item.ledger_date,
            currency=item.currency,
            entry_type=item.entry_type,
            amount=item.amount,
            linked_transaction_id=item.transaction_id,
            note=f"{item.transaction_type} {item.asset_symbol}",
        )
        entry.full_clean()
        entry.save()
        created += 1

    return {
        "portfolio_id": portfolio.id,
        "created_count": created,
        "already_synced": plan.already_synced + (plan.create_count - created),
    }
