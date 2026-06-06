"""FX rate coverage diagnostics (read-only; DB cache only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from cash.models import CashLedgerEntry
from fx.lookup import get_fx_rate_on_date, load_fx_rate_maps
from fx.models import FXRate
from portfolios import dates as portfolio_dates
from portfolios.scope import ResolvedPortfolioScope
from portfolios.summary_service import fifo_eligible_queryset, portfolio_base_currency
from settings_app.services import get_settings
from transactions.models import Transaction


@dataclass(frozen=True)
class FxCoverageGap:
    from_currency: str
    to_currency: str
    context: str
    earliest_date_needed: date | None
    latest_cached_date: date | None
    sample_missing_date: date | None
    detail: str


def _latest_fx_date(from_ccy: str, to_ccy: str) -> date | None:
    direct = (
        FXRate.objects.filter(from_currency=from_ccy, to_currency=to_ccy)
        .order_by("-date")
        .values_list("date", flat=True)
        .first()
    )
    if direct:
        return direct
    inverse = (
        FXRate.objects.filter(from_currency=to_ccy, to_currency=from_ccy)
        .order_by("-date")
        .values_list("date", flat=True)
        .first()
    )
    return inverse


def _check_pair_on_date(
    from_ccy: str,
    to_ccy: str,
    needed_date: date,
    *,
    context: str,
    fx_maps: dict,
) -> FxCoverageGap | None:
    if from_ccy == to_ccy:
        return None
    from fx.lookup import convert_amount_with_fill_from_maps

    converted, status = convert_amount_with_fill_from_maps(
        1, from_ccy, to_ccy, needed_date, fx_maps
    )
    if converted is not None:
        return None
    latest = _latest_fx_date(from_ccy, to_ccy)
    has_same_date = get_fx_rate_on_date(from_ccy, to_ccy, needed_date) is not None
    return FxCoverageGap(
        from_currency=from_ccy,
        to_currency=to_ccy,
        context=context,
        earliest_date_needed=needed_date,
        latest_cached_date=latest,
        sample_missing_date=needed_date if not has_same_date else None,
        detail=(
            f"No FX (with 7-day fill) from {from_ccy} to {to_ccy} for {needed_date}"
        ),
    )


def check_fx_coverage(
    *,
    user: AbstractBaseUser,
    scope: ResolvedPortfolioScope,
    display_currency: str | None,
    today: date | None = None,
) -> list[FxCoverageGap]:
    disp = (display_currency or get_settings(user).display_currency or "EUR").upper()
    as_of = today or portfolio_dates.current_date()
    gaps: list[FxCoverageGap] = []
    seen: set[tuple[str, str, str, str]] = set()

    cash_currencies = set(
        CashLedgerEntry.objects.filter(portfolio_id__in=scope.portfolio_ids)
        .values_list("currency", flat=True)
        .distinct()
    )

    queryset = fifo_eligible_queryset(scope.portfolio_ids)
    all_txns = list(queryset)
    txn_currencies = {t.currency.upper() for t in all_txns if t.currency}
    portfolio_bases: set[str] = set()
    if all_txns:
        portfolio_bases.add(portfolio_base_currency(all_txns).upper())

    needed_pairs: list[tuple[str, str, date, str]] = []
    for ccy in sorted(cash_currencies | txn_currencies | portfolio_bases):
        if ccy != disp:
            needed_pairs.append((ccy, disp, as_of, "display_conversion"))

    if all_txns:
        earliest = min(t.date for t in all_txns)
        for ccy in sorted(txn_currencies | portfolio_bases):
            if ccy != disp:
                needed_pairs.append((ccy, disp, earliest, "historical_flow"))

    if not needed_pairs:
        return []

    all_dates = [p[2] for p in needed_pairs]
    fx_start = min(all_dates) - timedelta(days=7)
    fx_end = max(all_dates)
    pair_set = {(a, b) for a, b, _, _ in needed_pairs}
    fx_maps = load_fx_rate_maps(pair_set, fx_start, fx_end)

    for from_ccy, to_ccy, needed_date, context in needed_pairs:
        key = (from_ccy, to_ccy, context, needed_date.isoformat())
        if key in seen:
            continue
        seen.add(key)
        gap = _check_pair_on_date(
            from_ccy, to_ccy, needed_date, context=context, fx_maps=fx_maps
        )
        if gap is not None:
            gaps.append(gap)

    return gaps


def build_fx_coverage_report(gaps: list[FxCoverageGap]) -> dict[str, Any]:
    return {
        "gap_count": len(gaps),
        "gaps": [asdict(g) for g in gaps],
    }


def format_fx_coverage_report(
    gaps: list[FxCoverageGap],
    *,
    display_currency: str,
) -> None:
    print("\n=== Summary ===")
    print(f"  display_currency={display_currency}")
    print(f"  fx_gaps: {len(gaps)}")
    if not gaps:
        print("\n(no FX coverage gaps detected for requested display currency)")
        return
    print("\n=== Gaps ===")
    for gap in gaps:
        print(
            f"  {gap.from_currency}->{gap.to_currency} [{gap.context}] "
            f"needed~={gap.earliest_date_needed} latest_cached={gap.latest_cached_date}: "
            f"{gap.detail}"
        )
