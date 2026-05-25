from __future__ import annotations

from decimal import Decimal

from finance.types import Transaction, TransactionType


def _split_factor(split: Transaction) -> Decimal | None:
    if split.split_from is None or split.split_to is None:
        return None
    if split.split_from <= 0 or split.split_to <= 0:
        return None
    return split.split_to / split.split_from


def apply_stock_split_adjustments(transactions: list[Transaction]) -> list[Transaction]:
    """
    Return BUY/SELL transactions with quantities/prices adjusted for prior STOCK_SPLIT rows.

    - Split factor = split_to / split_from per valid split row.
    - Only transactions with the same asset_symbol and date strictly before the split date.
    - STOCK_SPLIT rows are omitted from the result.
    - Invalid split_from/split_to are ignored.
    """
    splits = [
        t
        for t in transactions
        if t.type == TransactionType.STOCK_SPLIT and _split_factor(t) is not None
    ]
    adjusted: list[Transaction] = []

    for t in transactions:
        if t.type == TransactionType.STOCK_SPLIT:
            continue
        if t.type not in (TransactionType.BUY, TransactionType.SELL):
            adjusted.append(t)
            continue

        factor = Decimal("1")
        txn_sym = (t.asset_symbol or "").strip()
        for split in splits:
            split_sym = (split.asset_symbol or "").strip()
            if not split_sym or not txn_sym or split_sym != txn_sym:
                continue
            if t.date < split.date:
                sf = _split_factor(split)
                if sf is not None:
                    factor *= sf

        if factor == Decimal("1"):
            adjusted.append(t)
            continue

        adjusted.append(
            Transaction(
                type=t.type,
                date=t.date,
                quantity=t.quantity * factor,
                price=t.price / factor,
                fees=t.fees,
                asset_symbol=t.asset_symbol,
                split_from=t.split_from,
                split_to=t.split_to,
            )
        )

    return sorted(adjusted, key=lambda x: x.date)
