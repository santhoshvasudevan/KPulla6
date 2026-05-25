from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Optional


@dataclass(frozen=True)
class TwrorPoint:
    date: date
    value: Optional[Decimal]


def compute_twror_series(
    timeseries: list[dict],
    flows_by_date: Mapping[date, Decimal],
    *,
    flows_unknown_from: Optional[date] = None,
) -> list[TwrorPoint]:
    """
    Chain-link TWROR over a daily valuation series (one row per calendar day).

  Each timeseries row must include:
    - ``date``: ISO date string (YYYY-MM-DD)
    - ``portfolio_value``: end-of-day value or None when unknown

    Period return: (pv - flow - prev_value) / prev_value
    TWROR output is cumulative (factor - 1) * 100 as percentage points.
    """

    def _flows_known(d: date) -> bool:
        return flows_unknown_from is None or d < flows_unknown_from

    twror_factor = Decimal("1")
    out: list[TwrorPoint] = []
    prev_date: Optional[date] = None
    prev_value: Optional[Decimal] = None

    for row in timeseries:
        d = date.fromisoformat(row["date"])
        pv_raw = row.get("portfolio_value")
        pv = Decimal(str(pv_raw)) if pv_raw is not None else None

        if prev_date is None:
            out.append(TwrorPoint(date=d, value=None))
            prev_date = d
            prev_value = pv
            continue

        if pv is None or prev_value is None or prev_value <= 0 or not _flows_known(d):
            out.append(TwrorPoint(date=d, value=None))
            prev_date = d
            prev_value = pv
            continue

        flow = flows_by_date.get(d, Decimal("0"))
        period_return = (pv - flow - prev_value) / prev_value
        twror_factor *= Decimal("1") + period_return
        out.append(
            TwrorPoint(
                date=d,
                value=(twror_factor - Decimal("1")) * Decimal("100"),
            )
        )
        prev_date = d
        prev_value = pv

    return out
