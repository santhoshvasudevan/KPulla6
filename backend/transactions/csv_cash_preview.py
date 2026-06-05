"""CSV import cash shortfall preview and simulation (Cash-5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from finance.cash import (
    CashLedgerPoint,
    cash_balance_on_date,
    mf_buy_cash_required,
    mf_sell_cash_proceeds,
    stock_buy_cash_required,
    stock_sell_cash_proceeds,
)
from cash.services import list_ledger_points_for_portfolio
from portfolios.models import Portfolio
from transactions.models import TransactionType

_CSV_DEPOSIT_SOURCE = "CSV import cash deposit"
_CSV_DEPOSIT_NOTE = "Auto-proposed before CSV import"
_ZERO = Decimal("0")


@dataclass
class CsvCashShortfallRow:
    portfolio_id: int
    portfolio_name: str
    date: date
    currency: str
    required: Decimal
    available_before: Decimal
    shortfall: Decimal
    reason: str


@dataclass
class CsvProposedDeposit:
    portfolio_id: int
    portfolio_name: str
    date: date
    currency: str
    amount: Decimal
    source_of_funds: str = _CSV_DEPOSIT_SOURCE
    note: str = _CSV_DEPOSIT_NOTE


@dataclass
class CsvCashPreviewSummary:
    rows: int = 0
    cash_aware_rows: int = 0
    proposed_deposit_count: int = 0
    total_shortfall_by_currency: list[tuple[str, Decimal]] = field(default_factory=list)


@dataclass
class CsvCashPreviewResult:
    cash_aware: bool
    can_import_without_deposits: bool
    shortfalls: list[CsvCashShortfallRow] = field(default_factory=list)
    proposed_deposits: list[CsvProposedDeposit] = field(default_factory=list)
    row_errors: list[dict[str, Any]] = field(default_factory=list)
    summary: CsvCashPreviewSummary = field(default_factory=CsvCashPreviewSummary)


class CsvImportCashPreviewRequired(Exception):
    """Cash-aware import blocked until user confirms proposed deposits."""

    def __init__(self, preview: CsvCashPreviewResult) -> None:
        self.preview = preview
        super().__init__("CSV import requires cash deposit confirmation")


@dataclass(frozen=True)
class _SimRow:
    sort_date: date
    order: int
    currency: str
    txn_type: str
    reason: str
    # stock
    quantity: Decimal | None = None
    price_per_share: Decimal | None = None
    fees: Decimal | None = None
    paid_value: Decimal | None = None
    units_allotted: Decimal | None = None
    nav: Decimal | None = None


def _stock_sim_row(payload: dict[str, Any], order: int) -> _SimRow | None:
    txn_type = payload["type"]
    symbol = payload["asset_symbol"]
    d = payload["date"]
    currency = (payload.get("currency") or "EUR").strip().upper()
    reason = f"{txn_type} {symbol}"

    if txn_type in {TransactionType.STOCK_SPLIT, TransactionType.DIVIDEND}:
        return _SimRow(
            sort_date=d,
            order=order,
            currency=currency,
            txn_type=txn_type,
            reason=reason,
        )

    return _SimRow(
        sort_date=d,
        order=order,
        currency=currency,
        txn_type=txn_type,
        reason=reason,
        quantity=payload.get("quantity"),
        price_per_share=payload.get("price_per_share"),
        fees=payload.get("fees") or _ZERO,
    )


def _mf_sim_row(payload: dict[str, Any], order: int) -> _SimRow:
    txn_type = payload["type"]
    symbol = payload.get("scheme_code") or payload.get("scheme_name") or "MF"
    ledger_date = payload["investment_date"]
    currency = (payload.get("currency") or "INR").strip().upper()
    return _SimRow(
        sort_date=ledger_date,
        order=order,
        currency=currency,
        txn_type=txn_type,
        reason=f"{txn_type} {symbol}",
        paid_value=payload.get("paid_value"),
        units_allotted=payload.get("units_allotted"),
        nav=payload.get("nav"),
        fees=payload.get("fees") or _ZERO,
    )


def _build_sim_rows(
    csv_format: str, payloads: list[dict[str, Any]]
) -> list[_SimRow]:
    rows: list[_SimRow] = []
    for idx, payload in enumerate(payloads):
        if csv_format == "stock":
            row = _stock_sim_row(payload, idx)
            if row is not None:
                rows.append(row)
        elif csv_format == "mf":
            rows.append(_mf_sim_row(payload, idx))
    rows.sort(key=lambda r: (r.sort_date, r.order))
    return rows


def _cash_effect(row: _SimRow) -> tuple[Decimal | None, bool]:
    """Return (signed ledger amount, is_buy) or (None, False) when no cash movement."""
    if row.txn_type in {TransactionType.STOCK_SPLIT, TransactionType.DIVIDEND}:
        return None, False

    if row.txn_type == TransactionType.BUY:
        if row.paid_value is not None:
            required = mf_buy_cash_required(row.paid_value)
        else:
            required = stock_buy_cash_required(
                row.quantity or _ZERO,
                row.price_per_share or _ZERO,
                row.fees or _ZERO,
            )
        return -required, True

    if row.txn_type == TransactionType.SELL:
        if row.paid_value is not None:
            proceeds = mf_sell_cash_proceeds(
                paid_value=row.paid_value,
                units_allotted=row.units_allotted or _ZERO,
                nav=row.nav or _ZERO,
                fees=row.fees or _ZERO,
            )
        else:
            proceeds = stock_sell_cash_proceeds(
                row.quantity or _ZERO,
                row.price_per_share or _ZERO,
                row.fees or _ZERO,
            )
        if proceeds <= 0:
            return None, False
        return proceeds, False

    return None, False


def _merge_proposed_deposits(
    deposits: list[CsvProposedDeposit],
) -> list[CsvProposedDeposit]:
    merged: dict[tuple[int, date, str], Decimal] = {}
    for dep in deposits:
        key = (dep.portfolio_id, dep.date, dep.currency)
        merged[key] = merged.get(key, _ZERO) + dep.amount
    name_by_key = {
        (d.portfolio_id, d.date, d.currency): d.portfolio_name for d in deposits
    }
    return [
        CsvProposedDeposit(
            portfolio_id=pid,
            portfolio_name=name_by_key.get((pid, d, ccy), ""),
            date=d,
            currency=ccy,
            amount=amt,
            source_of_funds=_CSV_DEPOSIT_SOURCE,
            note=_CSV_DEPOSIT_NOTE,
        )
        for (pid, d, ccy), amt in sorted(merged.items())
    ]


def simulate_csv_cash_preview(
    portfolio: Portfolio,
    *,
    csv_format: str,
    payloads: list[dict[str, Any]],
) -> CsvCashPreviewResult:
    """Simulate chronological cash effects; propose same-currency deposits for BUY gaps."""
    if not portfolio.cash_aware_enabled:
        return CsvCashPreviewResult(
            cash_aware=False,
            can_import_without_deposits=True,
            summary=CsvCashPreviewSummary(rows=len(payloads), cash_aware_rows=0),
        )

    sim_rows = _build_sim_rows(csv_format, payloads)
    existing = list_ledger_points_for_portfolio(portfolio)
    simulated: list[CashLedgerPoint] = list(existing)
    shortfalls: list[CsvCashShortfallRow] = []
    raw_deposits: list[CsvProposedDeposit] = []

    for row in sim_rows:
        amount, is_buy = _cash_effect(row)
        if amount is None:
            continue

        if is_buy:
            required = abs(amount)
            available = cash_balance_on_date(simulated, row.sort_date).get(
                row.currency, _ZERO
            )
            if available < required:
                gap = required - available
                shortfalls.append(
                    CsvCashShortfallRow(
                        portfolio_id=portfolio.id,
                        portfolio_name=portfolio.name,
                        date=row.sort_date,
                        currency=row.currency,
                        required=required,
                        available_before=available,
                        shortfall=gap,
                        reason=row.reason,
                    )
                )
                raw_deposits.append(
                    CsvProposedDeposit(
                        portfolio_id=portfolio.id,
                        portfolio_name=portfolio.name,
                        date=row.sort_date,
                        currency=row.currency,
                        amount=gap,
                    )
                )
                simulated.append(
                    CashLedgerPoint(
                        date=row.sort_date,
                        currency=row.currency,
                        amount=gap,
                    )
                )
            simulated.append(
                CashLedgerPoint(
                    date=row.sort_date,
                    currency=row.currency,
                    amount=amount,
                )
            )
        else:
            simulated.append(
                CashLedgerPoint(
                    date=row.sort_date,
                    currency=row.currency,
                    amount=amount,
                )
            )

    proposed = _merge_proposed_deposits(raw_deposits)
    totals: dict[str, Decimal] = {}
    for sf in shortfalls:
        totals[sf.currency] = totals.get(sf.currency, _ZERO) + sf.shortfall

    return CsvCashPreviewResult(
        cash_aware=True,
        can_import_without_deposits=len(shortfalls) == 0,
        shortfalls=shortfalls,
        proposed_deposits=proposed,
        summary=CsvCashPreviewSummary(
            rows=len(payloads),
            cash_aware_rows=len(sim_rows),
            proposed_deposit_count=len(proposed),
            total_shortfall_by_currency=sorted(totals.items()),
        ),
    )


def preview_to_response_dict(preview: CsvCashPreviewResult) -> dict[str, Any]:
    return {
        "cash_aware": preview.cash_aware,
        "can_import_without_deposits": preview.can_import_without_deposits,
        "shortfalls": [
            {
                "portfolio_id": s.portfolio_id,
                "portfolio_name": s.portfolio_name,
                "date": s.date.isoformat(),
                "currency": s.currency,
                "required": float(s.required),
                "available_before": float(s.available_before),
                "shortfall": float(s.shortfall),
                "reason": s.reason,
            }
            for s in preview.shortfalls
        ],
        "proposed_deposits": [
            {
                "portfolio_id": d.portfolio_id,
                "portfolio_name": d.portfolio_name,
                "date": d.date.isoformat(),
                "currency": d.currency,
                "amount": float(d.amount),
                "source_of_funds": d.source_of_funds,
                "note": d.note,
            }
            for d in preview.proposed_deposits
        ],
        "row_errors": preview.row_errors,
        "summary": {
            "rows": preview.summary.rows,
            "cash_aware_rows": preview.summary.cash_aware_rows,
            "proposed_deposit_count": preview.summary.proposed_deposit_count,
            "total_shortfall_by_currency": [
                {"currency": ccy, "amount": float(amt)}
                for ccy, amt in preview.summary.total_shortfall_by_currency
            ],
        },
    }
