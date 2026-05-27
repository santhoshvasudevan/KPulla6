from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from finance.splits import apply_stock_split_adjustments
from finance.types import Transaction, TransactionType


@dataclass(frozen=True)
class FifoCostBasisMetrics:
    cumulative_qty: Decimal
    cumulative_invested_amount: Decimal
    avg_cost_per_share: Decimal
    realized_pl: Decimal
    unrealized_pl: Decimal


@dataclass
class _Lot:
    qty: Decimal
    unit_cost: Decimal


def _zero_metrics() -> FifoCostBasisMetrics:
    z = Decimal("0")
    return FifoCostBasisMetrics(
        cumulative_qty=z,
        cumulative_invested_amount=z,
        avg_cost_per_share=z,
        realized_pl=z,
        unrealized_pl=z,
    )


def build_split_adjusted_lot_snapshots(
    transactions: Iterable[Transaction],
) -> tuple[dict[date, Decimal], dict[date, Decimal]]:
    """
    Per-transaction-date cumulative qty and invested amount after split-adjusted FIFO.

    Use with split-adjusted historical prices (e.g. yfinance cache): pre-split BUY/SELL
    quantities are scaled so ``qty * price`` stays economically consistent across splits.
    """
    txns = apply_stock_split_adjustments(list(transactions))
    timeline: dict[date, Decimal] = {}
    inv_timeline: dict[date, Decimal] = {}
    lots: list[_Lot] = []

    for t in sorted(txns, key=lambda x: x.date):
        if t.type == TransactionType.BUY:
            if t.quantity > 0:
                lots.append(_Lot(qty=t.quantity, unit_cost=t.price))
        elif t.type == TransactionType.SELL:
            remaining = t.quantity
            while remaining > 0 and lots:
                lot = lots[0]
                take = min(lot.qty, remaining)
                lot.qty -= take
                remaining -= take
                if lot.qty <= 0:
                    lots.pop(0)
        cum_qty = sum((lot.qty for lot in lots), Decimal("0"))
        cum_inv = sum((lot.qty * lot.unit_cost for lot in lots), Decimal("0"))
        timeline[t.date] = cum_qty
        inv_timeline[t.date] = cum_inv

    return timeline, inv_timeline


def calculate_fifo_cost_basis_metrics(
    transactions: Iterable[Transaction],
    *,
    current_price: Optional[Decimal] = None,
) -> FifoCostBasisMetrics:
    """
    FIFO cost basis metrics for a single asset.

    Fees are intentionally ignored (consistent with KPulla5 fifo.py).
    DIVIDEND and STOCK_SPLIT rows are not BUY/SELL cash flows; splits adjust via
    apply_stock_split_adjustments() before lot processing.
    """
    txns = apply_stock_split_adjustments(list(transactions))
    if not txns:
        return _zero_metrics()

    lots: list[_Lot] = []
    realized = Decimal("0")

    for t in sorted(txns, key=lambda x: x.date):
        if t.type == TransactionType.BUY:
            if t.quantity <= 0:
                continue
            lots.append(_Lot(qty=t.quantity, unit_cost=t.price))
        elif t.type == TransactionType.SELL:
            sell_qty = t.quantity
            if sell_qty <= 0:
                continue
            proceeds = sell_qty * t.price
            remaining = sell_qty
            fifo_cost_sold = Decimal("0")

            while remaining > 0 and lots:
                lot = lots[0]
                take = min(lot.qty, remaining)
                fifo_cost_sold += take * lot.unit_cost
                lot.qty -= take
                remaining -= take
                if lot.qty <= 0:
                    lots.pop(0)

            realized += proceeds - fifo_cost_sold
        else:
            continue

    qty = sum((lot.qty for lot in lots), Decimal("0"))
    invested = sum((lot.qty * lot.unit_cost for lot in lots), Decimal("0"))

    if qty <= 0:
        return FifoCostBasisMetrics(
            cumulative_qty=Decimal("0"),
            cumulative_invested_amount=Decimal("0"),
            avg_cost_per_share=Decimal("0"),
            realized_pl=realized,
            unrealized_pl=Decimal("0"),
        )

    avg_cost = invested / qty
    px = current_price if current_price is not None else Decimal("0")
    unrealized = px * qty - invested

    return FifoCostBasisMetrics(
        cumulative_qty=qty,
        cumulative_invested_amount=invested,
        avg_cost_per_share=avg_cost,
        realized_pl=realized,
        unrealized_pl=unrealized,
    )
