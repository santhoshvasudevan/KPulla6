from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class TransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    STOCK_SPLIT = "STOCK_SPLIT"


@dataclass(frozen=True)
class Transaction:
    """Framework-independent transaction DTO for finance calculations."""

    type: TransactionType
    date: date
    quantity: Decimal
    price: Decimal
    fees: Decimal = field(default_factory=lambda: Decimal("0"))
    asset_symbol: Optional[str] = None
    split_from: Optional[Decimal] = None
    split_to: Optional[Decimal] = None
