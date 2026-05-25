from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class DailyPrice:
    date: date
    close: Decimal
    currency: str


class PriceProvider(Protocol):
    def fetch_history(
        self, symbol: str, start: date, end: date
    ) -> tuple[list[DailyPrice], str | None]:
        """Return daily closes and optional quote currency for the symbol."""
