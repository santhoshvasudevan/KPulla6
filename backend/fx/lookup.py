from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fx.models import FXRate


def _norm_ccy(value: str | None) -> str:
    return (value or "").strip().upper()


def get_fx_rate_on_date(
    from_currency: str, to_currency: str, d: date
) -> Optional[Decimal]:
    """
    Same-date FX only (no latest-rate fallback for historical dates).
    Returns direct rate from_currency -> to_currency, or inverse-derived rate.
    """
    frm = _norm_ccy(from_currency)
    to = _norm_ccy(to_currency)
    if not frm or not to:
        return None
    if frm == to:
        return Decimal("1")

    direct = FXRate.objects.filter(
        from_currency=frm, to_currency=to, date=d
    ).first()
    if direct is not None:
        return direct.rate

    inverse = FXRate.objects.filter(
        from_currency=to, to_currency=frm, date=d
    ).first()
    if inverse is not None and inverse.rate != 0:
        return Decimal("1") / inverse.rate

    return None


def convert_amount_on_date(
    amount: float | Decimal,
    from_currency: str,
    to_currency: str,
    d: date,
) -> tuple[Optional[Decimal], str]:
    """Convert using same-date FX only. Status is ok or fx_unavailable."""
    frm = _norm_ccy(from_currency)
    to = _norm_ccy(to_currency)
    if frm == to:
        return Decimal(str(amount)), "ok"

    rate = get_fx_rate_on_date(frm, to, d)
    if rate is None:
        return None, "fx_unavailable"
    return Decimal(str(amount)) * rate, "ok"


def convert_amount_with_fill(
    amount: float | Decimal,
    from_currency: str,
    to_currency: str,
    d: date,
    *,
    max_fill_days: int = 7,
) -> tuple[Optional[Decimal], str]:
    """
    Convert using same-date FX, falling back to prior dates within max_fill_days.
    Used for summary display-currency conversion (KPulla5-compatible).
    """
    value, status = convert_amount_on_date(amount, from_currency, to_currency, d)
    if value is not None:
        return value, status
    for days_back in range(1, max_fill_days + 1):
        prev = d - timedelta(days=days_back)
        value, status = convert_amount_on_date(amount, from_currency, to_currency, prev)
        if value is not None:
            return value, "filled"
    return None, "fx_unavailable"


def convert_amount_with_fill_from_maps(
    amount: float | Decimal,
    from_currency: str,
    to_currency: str,
    d: date,
    fx_maps: dict[tuple[str, str], dict[date, Decimal]],
    *,
    max_fill_days: int = 7,
) -> tuple[Optional[Decimal], str]:
    """Same semantics as convert_amount_with_fill using preloaded FX maps (no DB)."""
    frm = _norm_ccy(from_currency)
    to = _norm_ccy(to_currency)
    if frm == to:
        return Decimal(str(amount)), "ok"
    fx_rate, status = fx_lookup_from_maps(
        fx_maps, frm, to, d, max_fill_days=max_fill_days
    )
    if fx_rate is None:
        return None, status
    return Decimal(str(amount)) * fx_rate, status


def load_fx_rate_maps(
    pairs: set[tuple[str, str]],
    start: date,
    end: date,
) -> dict[tuple[str, str], dict[date, Decimal]]:
    """Bulk-load FX rows for pairs into nested dicts (includes inverse rates)."""
    if not pairs:
        return {}
    from django.db.models import Q

    clauses = Q()
    for frm, to in pairs:
        if frm and to and frm != to:
            clauses |= Q(from_currency=frm, to_currency=to) | Q(
                from_currency=to, to_currency=frm
            )
    if not clauses:
        return {}

    rows = FXRate.objects.filter(clauses, date__gte=start, date__lte=end)
    out: dict[tuple[str, str], dict[date, Decimal]] = {}
    for row in rows:
        out.setdefault((row.from_currency, row.to_currency), {})[row.date] = row.rate
        if row.rate and row.rate != 0:
            out.setdefault((row.to_currency, row.from_currency), {})[row.date] = (
                Decimal("1") / row.rate
            )
    return out


def fx_lookup_from_maps(
    fx_maps: dict[tuple[str, str], dict[date, Decimal]],
    from_currency: str,
    to_currency: str,
    d: date,
    *,
    max_fill_days: int = 7,
) -> tuple[Optional[Decimal], str]:
    frm = _norm_ccy(from_currency)
    to = _norm_ccy(to_currency)
    if frm == to:
        return Decimal("1"), "ok"
    m = fx_maps.get((frm, to), {})
    if d in m:
        return m[d], "ok"
    for days_back in range(1, max_fill_days + 1):
        prev = d - timedelta(days=days_back)
        if prev in m:
            return m[prev], "filled"
    return None, "fx_unavailable"
