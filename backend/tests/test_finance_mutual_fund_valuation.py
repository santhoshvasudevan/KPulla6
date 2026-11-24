"""Pure provisional/provider NAV resolution and market value (finance layer)."""
from datetime import date
from decimal import Decimal

import pytest

from finance.mutual_fund_valuation import (
    PROVIDER_CACHE,
    PROVISIONAL_USER,
    calculate_mutual_fund_market_value,
    collapse_provisional_observations,
    merge_nav_timeline,
    resolve_nav_point,
)

D10, D12, D16 = date(2026, 3, 10), date(2026, 3, 12), date(2026, 3, 16)


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
