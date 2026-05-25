from __future__ import annotations

from decimal import Decimal

from finance.splits import apply_stock_split_adjustments
from finance.types import Transaction, TransactionType


def detect_oversell(transactions: list[Transaction]) -> bool:
    """
    True when a SELL quantity exceeds available lots at that point in time
    (after split adjustments). Matches KPulla5 FIFO oversell semantics.
    """
    txns = apply_stock_split_adjustments(transactions)
    held = Decimal("0")
    for t in sorted(txns, key=lambda x: (x.date, x.type.value)):
        if t.type == TransactionType.BUY:
            if t.quantity > 0:
                held += t.quantity
        elif t.type == TransactionType.SELL:
            if t.quantity <= 0:
                continue
            if t.quantity > held:
                return True
            held -= t.quantity
    return False
