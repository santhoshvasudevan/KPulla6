"""Pure provisional/provider NAV resolution and market value (finance layer)."""
import ast
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import finance.mutual_fund_valuation as mf_valuation
from finance.mutual_fund_valuation import (
    MIXED,
    PROVIDER_CACHE,
    PROVISIONAL_USER,
    MutualFundUnitEvent,
    calculate_mutual_fund_market_value,
    collapse_provisional_observations,
    daily_mutual_fund_values,
    folio_unit_timelines,
    merge_nav_timeline,
    provisional_navs_by_folio,
    resolve_nav_point,
    valuation_legs,
    value_scoped_mutual_fund_holding,
)
from finance.types import Transaction, TransactionType

BUY, SELL = TransactionType.BUY, TransactionType.SELL
D10, D11, D12, D16 = date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12), date(2026, 3, 16)


def trade(day, units, nav="40", *, type=BUY, folio=1, seq=0, provisional=False):
    return MutualFundUnitEvent(
        trade_date=day, sequence=seq, folio_id=folio, type=type, units=Decimal(units),
        nav_date=day, nav=Decimal(nav), provisional=provisional,
    )


def fifo_dtos(events):
    ordered = sorted(events, key=lambda e: (e.trade_date, e.sequence))
    return [Transaction(type=e.type, date=e.trade_date, quantity=e.units, price=e.nav) for e in ordered]


def scoped(events, provider_point):
    return value_scoped_mutual_fund_holding(events, fifo_dtos(events), provider_point=provider_point)


def test_market_value_rounds_half_up_to_four_places():
    assert calculate_mutual_fund_market_value(Decimal("15.2885"), Decimal("65.4321")) == Decimal("1000.3587")
    assert calculate_mutual_fund_market_value(Decimal("0.00005"), Decimal("1")) == Decimal("0.0001")


@pytest.mark.parametrize("nav, units", [("0", "1"), ("-1", "1"), ("1", "0"), ("NaN", "1")])
def test_market_value_rejects_non_positive_inputs(nav, units):
    with pytest.raises(ValueError):
        calculate_mutual_fund_market_value(Decimal(nav), Decimal(units))


def test_same_date_conflict_is_kept_not_averaged():
    collapsed = collapse_provisional_observations(
        [(D12, Decimal("42.5")), (D12, Decimal("42.5")), (D16, Decimal("43")), (D16, Decimal("44"))]
    )
    assert collapsed == {D12: Decimal("42.5"), D16: None}


def test_newer_provisional_beats_older_provider_until_next_provider():
    provisional = {D12: Decimal("42.5")}
    point = resolve_nav_point((D10, Decimal("40")), provisional)
    assert (point.nav_date, point.nav, point.source) == (D12, Decimal("42.5"), PROVISIONAL_USER)
    point = resolve_nav_point((D16, Decimal("45")), provisional)
    assert (point.nav, point.source) == (Decimal("45"), PROVIDER_CACHE)
    point = resolve_nav_point((D12, Decimal("41")), provisional)
    assert (point.nav, point.source) == (Decimal("41"), PROVIDER_CACHE)
    assert resolve_nav_point((D10, Decimal("40")), provisional, as_of=D10).source == PROVIDER_CACHE


def test_merged_timeline_prefers_provider_on_same_date():
    timeline = merge_nav_timeline({D10: Decimal("40"), D12: Decimal("41")}, {D12: Decimal("42.5"), D16: None})
    assert timeline[D12].source == PROVIDER_CACHE and timeline[D12].nav == Decimal("41")
    assert timeline[D16].conflict


# --- unit replay ---------------------------------------------------------------------


def test_unit_replay_orders_same_day_by_sequence_and_floors_each_folio_at_zero():
    events = [
        trade(D10, "10.1234", folio=1, seq=2),
        trade(D10, "4", type=SELL, folio=1, seq=1),   # earlier sequence: nothing held yet
        trade(D12, "3.0001", type=SELL, folio=1, seq=3),
        trade(D11, "5", folio=2, seq=4),
        trade(D12, "7", type=SELL, folio=2, seq=5),   # oversold folio floors at zero
    ]
    assert folio_unit_timelines(events) == {
        1: {D10: Decimal("10.1234"), D12: Decimal("7.1233")},
        2: {D11: Decimal("5"), D12: Decimal("0")},
    }


def test_only_provisional_buys_and_sells_contribute_folio_observations():
    events = [
        trade(D10, "100", "40", folio=1),
        trade(D12, "10", "42.5", folio=1, provisional=True),
        trade(D12, "5", "42.5", type=SELL, folio=1, provisional=True),
        trade(D12, "10", "43", folio=2, provisional=True),
    ]
    assert provisional_navs_by_folio(events) == {1: {D12: Decimal("42.5")}, 2: {D12: Decimal("43")}}


# --- scoped current valuation ---------------------------------------------------------


def test_provider_only_holding_values_open_units_at_cached_nav():
    events = [trade(D10, "12.3456", "40"), trade(D11, "0.0044", "41")]
    result = scoped(events, (D16, Decimal("45.6789")))
    assert result.current_value == Decimal("12.35") * Decimal("45.6789")
    assert (result.nav, result.nav_available, result.overlaid) == (Decimal("45.6789"), True, False)
    assert result.valuation.source == PROVIDER_CACHE and not result.valuation.provisional
    assert result.unrealized_pl == result.current_value - result.fifo.cumulative_invested_amount


def test_closed_holding_is_a_genuine_zero_that_keeps_the_provider_nav():
    events = [trade(D10, "100", "40"), trade(D12, "100", "42", type=SELL)]
    result = scoped(events, (D16, Decimal("45")))
    assert result.current_value == Decimal("0") and result.unrealized_pl == Decimal("0")
    assert (result.nav, result.valuation.nav_date) == (Decimal("45"), D16)
    assert result.fifo.realized_pl == Decimal("200")


def test_open_holding_without_any_nav_is_unavailable():
    result = scoped([trade(D10, "100", "40")], None)
    assert result.current_value is None and result.unrealized_pl is None
    assert (result.nav, result.nav_available) == (None, False)
    assert result.fifo.cumulative_invested_amount == Decimal("4000")


def test_newer_provisional_values_the_folio_until_the_provider_resumes():
    events = [trade(D10, "100", "40"), trade(D12, "40", "42.5", type=SELL, provisional=True)]
    result = scoped(events, (D10, Decimal("40")))
    assert result.current_value == Decimal("2550")  # 60 × 42.5
    assert (result.nav, result.overlaid) == (Decimal("42.5"), True)
    assert (result.valuation.source, result.valuation.provisional_dates) == (PROVISIONAL_USER, [D12])
    assert result.unrealized_pl == Decimal("2550") - Decimal("2400")

    resumed = scoped(events, (D16, Decimal("45")))
    assert resumed.current_value == Decimal("2700")  # 60 × 45
    assert (resumed.nav, resumed.overlaid, resumed.valuation.provisional) == (Decimal("45"), False, False)


def test_folios_are_valued_on_their_own_nav_without_averaging():
    events = [
        trade(D10, "100", "40", folio=1, seq=1),
        trade(D10, "100", "40", folio=2, seq=2),
        trade(D12, "10", "42.5", folio=1, seq=3, provisional=True),
    ]
    result = scoped(events, (D10, Decimal("40")))
    assert result.current_value == Decimal("8675")  # 110 × 42.5 + 100 × 40
    assert (result.valuation.source, result.valuation.nav_date, result.nav) == (MIXED, D12, None)
    assert result.nav_available is True
    assert result.unrealized_pl == Decimal("8675") - result.fifo.cumulative_invested_amount


def test_conflicting_folio_leaves_value_unavailable_without_older_provider_fallback():
    events = [
        trade(D10, "100", "40"),
        trade(D12, "10", "42.5", seq=1, provisional=True),
        trade(D12, "10", "43", seq=2, provisional=True),
    ]
    result = scoped(events, (D10, Decimal("40")))
    assert result.current_value is None and result.unrealized_pl is None
    assert (result.nav, result.nav_available, result.overlaid) == (None, False, True)
    assert result.valuation.conflict_dates == [D12]


def test_closed_provisional_folio_does_not_drive_the_open_folio():
    events = [
        trade(D10, "100", "40", folio=1, seq=1),
        trade(D12, "100", "42.5", type=SELL, folio=1, seq=2, provisional=True),
        trade(D10, "100", "40", folio=2, seq=3),
    ]
    result = scoped(events, (D10, Decimal("40")))
    assert result.current_value == Decimal("4000")
    assert result.valuation.source == PROVIDER_CACHE and result.valuation.provisional_dates == []


# --- daily valuation shares the same legs ----------------------------------------------


def _days(start, end):
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def test_daily_values_carry_per_unit_nav_resume_on_provider_and_match_current_value():
    events = [
        trade(D10, "100", "40", seq=1),
        trade(D12, "40", "42.5", type=SELL, seq=2, provisional=True),
    ]
    provider = {D11: Decimal("41"), D16: Decimal("45")}
    end = date(2026, 3, 17)
    daily = daily_mutual_fund_values(valuation_legs(events), provider, start=D10, end=end)
    assert list(daily) == _days(D10, end)
    assert daily[D10].nav_missing and daily[D10].value == Decimal("0")  # no NAV known yet
    assert (daily[D11].value, daily[D11].provisional) == (Decimal("4100"), False)
    assert (daily[D12].value, daily[D12].provisional) == (Decimal("2550"), True)
    assert daily[date(2026, 3, 15)].value == Decimal("2550")
    assert (daily[D16].value, daily[D16].provisional) == (Decimal("2700"), False)
    current = scoped(events, (D16, Decimal("45")))
    assert daily[end].value == current.current_value


def test_daily_values_report_conflicts_as_missing_and_bootstrap_before_window():
    events = [
        trade(D10, "100", "40", seq=1),
        trade(D12, "10", "42.5", seq=2, provisional=True),
        trade(D12, "10", "43", seq=3, provisional=True),
    ]
    daily = daily_mutual_fund_values(valuation_legs(events), {D10: Decimal("40")}, start=D11, end=D12)
    assert (daily[D11].value, daily[D11].nav_missing) == (Decimal("4000"), False)
    assert daily[D12].nav_missing and daily[D12].value == Decimal("0")


def test_daily_values_skip_closed_folios_and_sum_open_ones():
    events = [
        trade(D10, "100", "40", folio=1, seq=1),
        trade(D12, "100", "42.5", type=SELL, folio=1, seq=2, provisional=True),
        trade(D10, "100", "40", folio=2, seq=3),
        trade(D16, "10", "44", folio=2, seq=4, provisional=True),
    ]
    daily = daily_mutual_fund_values(valuation_legs(events), {D10: Decimal("40")}, start=D10, end=D16)
    assert daily[D11].value == Decimal("8000")
    assert (daily[D12].value, daily[D12].nav_missing, daily[D12].provisional) == (
        Decimal("4000"), False, False)
    assert (daily[D16].value, daily[D16].provisional) == (Decimal("4840"), True)


# --- framework boundary ----------------------------------------------------------------


def test_valuation_module_has_no_framework_or_database_imports():
    tree = ast.parse(Path(mf_valuation.__file__).read_text())
    modules = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    allowed_roots = {"__future__", "dataclasses", "datetime", "decimal", "typing", "finance"}
    assert {m.split(".")[0] for m in modules} <= allowed_roots
