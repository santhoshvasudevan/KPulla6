"""Shared helpers for parsing daily return inputs (no Django)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable, Optional, Union

from finance.returns import DailyReturnPoint

ReturnInput = Union[DailyReturnPoint, Optional[Decimal]]


def iter_return_points(
    daily_returns: Iterable[ReturnInput],
) -> list[tuple[Optional[date], Optional[Decimal]]]:
    """Normalize ``DailyReturnPoint`` or bare fractional returns to (date?, fraction)."""
    out: list[tuple[Optional[date], Optional[Decimal]]] = []
    for item in daily_returns:
        if isinstance(item, DailyReturnPoint):
            out.append((item.date, item.return_fraction))
        else:
            out.append((None, item))
    return out


def valid_fractions(daily_returns: Iterable[ReturnInput]) -> list[Decimal]:
    return [r for _, r in iter_return_points(daily_returns) if r is not None]
