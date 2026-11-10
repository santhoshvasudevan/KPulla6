"""Native-currency NAV returns, independent of personal transactions."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from finance.returns import DailyReturnPoint


@dataclass(frozen=True)
class NavReturnSeries:
    points: list[DailyReturnPoint]
    gaps: list[tuple[date, date]]


def nav_return_series(observations: list[tuple[date, Decimal]], *, start: date,
                      end: date, max_gap_days: int = 7) -> NavReturnSeries:
    """Never bridge unexplained long gaps or invent non-publication-day returns."""
    points = []
    gaps = []
    previous = None
    for day, value in sorted(observations):
        if day > end or value <= 0:
            continue
        if day >= start:
            fraction = None
            if previous is not None:
                previous_day, previous_value = previous
                if (day - previous_day).days <= max_gap_days:
                    fraction = value / previous_value - 1
                else:
                    gaps.append((previous_day, day))
            points.append(DailyReturnPoint(date=day, return_fraction=fraction))
        previous = (day, value)
    return NavReturnSeries(points=points, gaps=gaps)
