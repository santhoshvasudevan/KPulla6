"""Portfolio performance chart date-range resolution (server-side filtering)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

PerformanceRangeCode = Literal["7D", "30D", "YTD", "1Y", "3Y", "5Y", "ALL"]

VALID_PERFORMANCE_RANGES = frozenset({"7D", "30D", "YTD", "1Y", "3Y", "5Y", "ALL"})


class InvalidPerformanceRangeError(ValueError):
    pass


def validate_performance_range(code: str | None) -> str:
    c = (code or "1Y").strip().upper()
    if c not in VALID_PERFORMANCE_RANGES:
        raise InvalidPerformanceRangeError(f"Invalid range: {code!r}")
    return c


def resolve_performance_range_start(range_code: str, today: date, inception: date) -> date:
    """
    First calendar date to include in the chart. Never before portfolio inception.
    """
    if range_code == "ALL":
        return inception
    if range_code == "7D":
        start = today - timedelta(days=7)
    elif range_code == "30D":
        start = today - timedelta(days=30)
    elif range_code == "YTD":
        start = date(today.year, 1, 1)
    elif range_code == "1Y":
        start = today - timedelta(days=365)
    elif range_code == "3Y":
        start = today - timedelta(days=365 * 3)
    elif range_code == "5Y":
        start = today - timedelta(days=365 * 5)
    else:
        start = inception
    return max(inception, start)
