"""Cached NAV observations and coverage shared by asset and Compare analytics."""
from datetime import date, timedelta

from finance.nav_returns import nav_return_series
from finance.performance_range import resolve_performance_range_start
from market_data.models import AssetType, HistoricalPrice


def load_nav_observations(scheme: str, today: date):
    return list(HistoricalPrice.objects.filter(
        asset_symbol=scheme, asset_type=AssetType.MUTUAL_FUND,
        date__lte=today, close_price__gt=0,
    ).order_by("date").values_list("date", "close_price"))


def load_nav_performance(scheme: str, range_code: str, today: date):
    return prepare_nav_observations(load_nav_observations(scheme, today), range_code, today)


def prepare_nav_observations(observations, range_code: str, today: date, *, start_override=None):
    """Recompute returns and coverage after selecting common observation intervals."""
    if not observations:
        return [], [], {"start": None, "end": None, "requested_start": None, "partial_months": [],
                        "partial_years": [], "gaps": [], "incomplete": True}, [
                            "No cached NAV is available; run an explicit NAV refresh."]
    requested = resolve_performance_range_start(range_code, today, date.min)
    start = start_override or (observations[0][0] if range_code == "ALL" else requested)
    selected = [(d, n) for d, n in observations if d >= start]
    prior = [(d, n) for d, n in observations if d < start]
    inputs = prior[-1:] + selected
    series = nav_return_series(inputs, start=start, end=today)
    warnings = []
    opening_available = bool(prior and (start - prior[-1][0]).days <= 7)
    first = selected[0][0] if selected else None
    last = selected[-1][0] if selected else None
    incomplete = bool(series.gaps) or not selected
    if not any(p.return_fraction is not None for p in series.points):
        warnings.append("At least two eligible cached NAV observations are required for fund returns.")
    if range_code != "ALL" and not opening_available:
        incomplete = True
        warnings.append("Opening NAV coverage is incomplete for the requested range.")
    if series.gaps:
        warnings.append("NAV history has gaps longer than seven calendar days; affected returns are unavailable.")
    if not last or (today - last).days > 7:
        incomplete = True
        warnings.append("Latest cached NAV is stale or unavailable for this range.")
    partial_months = set()
    partial_years = set()
    if first:
        if start.day != 1 or not opening_available:
            partial_months.add(first.strftime("%Y-%m"))
        if (start.month, start.day) != (1, 1) or not opening_available:
            partial_years.add(str(first.year))
    if last:
        next_day = today + timedelta(days=1)
        if next_day.month == today.month or (today - last).days > 7:
            partial_months.add(last.strftime("%Y-%m"))
        if (today.month, today.day) != (12, 31) or (today - last).days > 7:
            partial_years.add(str(last.year))
    coverage = {"start": first.isoformat() if first else None,
                "end": last.isoformat() if last else None,
                "requested_start": start.isoformat(), "incomplete": incomplete,
                "partial_months": sorted(partial_months), "partial_years": sorted(partial_years),
                "gaps": [{"start": a.isoformat(), "end": b.isoformat()} for a, b in series.gaps]}
    values = [{"date": d.isoformat(), "portfolio_value": float(n)} for d, n in inputs]
    return series.points, values, coverage, warnings
