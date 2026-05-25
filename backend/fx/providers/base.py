from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class DailyFxRate:
    date: date
    rate: Decimal


class FxProvider(Protocol):
    def fetch_rates(
        self, from_currency: str, to_currency: str, start: date, end: date
    ) -> list[DailyFxRate]:
        """Return FX rates stored as from_currency -> to_currency."""
