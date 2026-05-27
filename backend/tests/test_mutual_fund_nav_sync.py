"""MF-2 — mutual fund NAV sync and lookup tests."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from market_data.models import Asset, AssetType, HistoricalPrice, MutualFundProfile, PrimaryAssetClass
from market_data.nav_lookup import latest_nav_for_asset, normalize_scheme_code
from market_data.nav_repository import list_mutual_fund_navs_in_range
from market_data.price_lookup import latest_historical_price
from market_data.providers.mutual_fund_nav_provider import NavPoint
from market_data.services.mutual_fund_nav_sync import sync_mutual_fund_navs, sync_one_mutual_fund
from portfolios.seed import ensure_default_portfolio
from transactions.models import (
    Folio,
    MutualFundTransactionDetail,
    Transaction,
    TransactionType,
)


class MockNavProvider:
    def __init__(
        self,
        histories: dict[str, list[NavPoint]] | None = None,
        *,
        fail: set[str] | None = None,
        latest: dict[str, NavPoint] | None = None,
    ):
        self.histories = histories or {}
        self.fail = fail or set()
        self.latest = latest or {}
        self.history_calls: list[tuple[str, date, date]] = []
        self.latest_calls: list[str] = []

    def get_latest_nav(self, scheme_code: str) -> NavPoint | None:
        self.latest_calls.append(scheme_code)
        if scheme_code in self.fail:
            raise RuntimeError(f"provider error for {scheme_code}")
        return self.latest.get(scheme_code)

    def get_nav_history(self, scheme_code: str, start: date, end: date) -> list[NavPoint]:
        self.history_calls.append((scheme_code, start, end))
        if scheme_code in self.fail:
            raise RuntimeError(f"provider error for {scheme_code}")
        rows = self.histories.get(scheme_code, [])
        return [r for r in rows if start <= r.date <= end]


def _mf_asset(*, scheme_code: str = "120503", **kwargs) -> Asset:
    defaults = {
        "asset_type": AssetType.MUTUAL_FUND,
        "symbol": scheme_code,
        "display_name": "Test Direct Growth Fund",
        "currency": "INR",
        "provider": "amfi",
        "provider_symbol": scheme_code,
        "primary_asset_class": PrimaryAssetClass.EQUITY,
        "region": "IN",
        "is_active": True,
    }
    defaults.update(kwargs)
    return Asset.objects.create(**defaults)


def _mf_profile(asset: Asset, **kwargs) -> MutualFundProfile:
    defaults = {
        "asset": asset,
        "scheme_code": asset.symbol,
        "scheme_name": asset.display_name or "Test Scheme",
    }
    defaults.update(kwargs)
    return MutualFundProfile.objects.create(**defaults)


def _mf_buy_with_detail(
    *,
    scheme_code: str = "120503",
    nav_date: date,
    investment_date: date | None = None,
):
    portfolio = ensure_default_portfolio()
    asset = Asset.objects.filter(
        asset_type=AssetType.MUTUAL_FUND,
        symbol=scheme_code,
    ).first()
    if asset is None:
        asset = _mf_asset(scheme_code=scheme_code)
        _mf_profile(asset)
    elif not MutualFundProfile.objects.filter(asset=asset).exists():
        _mf_profile(asset)
    folio, _ = Folio.objects.get_or_create(
        portfolio=portfolio,
        asset=asset,
        folio_number="FOLIO-001",
    )
    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol=scheme_code,
        date=nav_date,
        type=TransactionType.BUY,
        quantity=Decimal("100"),
        price_per_share=Decimal("42.50"),
        currency="INR",
    )
    MutualFundTransactionDetail.objects.create(
        transaction=txn,
        folio=folio,
        investment_date=investment_date or nav_date,
        nav_date=nav_date,
        nav=Decimal("42.50"),
        units_allotted=Decimal("100"),
        paid_value=Decimal("4255"),
        market_value=Decimal("4250"),
    )
    return asset


@pytest.mark.django_db
def test_normalize_scheme_code_strips_only():
    assert normalize_scheme_code(" 120503 ") == "120503"


@pytest.mark.django_db
def test_sync_creates_mutual_fund_historical_price_rows(seeded):
    today = date.today()
    asset = _mf_asset(scheme_code="120503")
    profile = _mf_profile(asset)
    _mf_buy_with_detail(scheme_code="120503", nav_date=today - timedelta(days=5))

    provider = MockNavProvider(
        {
            "120503": [
                NavPoint(today - timedelta(days=4), Decimal("43.00"), "INR"),
                NavPoint(today - timedelta(days=3), Decimal("43.50"), "INR"),
            ]
        }
    )
    assert sync_one_mutual_fund(profile, provider) is True
    rows = HistoricalPrice.objects.filter(
        asset_symbol="120503",
        asset_type=AssetType.MUTUAL_FUND,
    )
    assert rows.count() == 2
    row = rows.order_by("date").first()
    assert row.close_price == Decimal("43.00")
    assert row.currency == "INR"
    assert row.source == "amfi"
    assert row.asset_id == asset.id


@pytest.mark.django_db
def test_sync_incremental_from_latest_cached_plus_one(seeded):
    today = date.today()
    asset = _mf_asset(scheme_code="120503")
    profile = _mf_profile(asset)
    _mf_buy_with_detail(scheme_code="120503", nav_date=today - timedelta(days=10))
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=today - timedelta(days=6),
        close_price=Decimal("42.00"),
        currency="INR",
        asset_type=AssetType.MUTUAL_FUND,
        source="amfi",
        asset=asset,
    )
    provider = MockNavProvider(
        {
            "120503": [
                NavPoint(today - timedelta(days=5), Decimal("42.10"), "INR"),
                NavPoint(today - timedelta(days=4), Decimal("42.20"), "INR"),
            ]
        }
    )
    sync_one_mutual_fund(profile, provider)
    assert provider.history_calls[0][1] == today - timedelta(days=5)
    assert HistoricalPrice.objects.filter(asset_symbol="120503").count() == 3


@pytest.mark.django_db
def test_sync_idempotent(seeded):
    today = date.today()
    asset = _mf_asset(scheme_code="120503")
    profile = _mf_profile(asset)
    _mf_buy_with_detail(scheme_code="120503", nav_date=today - timedelta(days=5))
    d = today - timedelta(days=3)
    provider = MockNavProvider({"120503": [NavPoint(d, Decimal("44.00"), "INR")]})
    sync_one_mutual_fund(profile, provider)
    sync_one_mutual_fund(profile, provider)
    assert HistoricalPrice.objects.filter(asset_symbol="120503", date=d).count() == 1


@pytest.mark.django_db
def test_sync_skips_profile_without_transaction_or_cached_nav(seeded):
    asset = _mf_asset(scheme_code="120503")
    profile = _mf_profile(asset)
    provider = MockNavProvider({"120503": [NavPoint(date.today(), Decimal("10"), "INR")]})
    result = sync_mutual_fund_navs(provider=provider)
    assert result.skipped >= 1
    assert provider.history_calls == []
    assert HistoricalPrice.objects.filter(asset_type=AssetType.MUTUAL_FUND).count() == 0


@pytest.mark.django_db
def test_sync_provider_failure_for_one_fund_does_not_fail_others(seeded):
    today = date.today()
    asset_a = _mf_asset(scheme_code="120503")
    profile_a = _mf_profile(asset_a)
    _mf_buy_with_detail(scheme_code="120503", nav_date=today - timedelta(days=5))

    asset_b = _mf_asset(scheme_code="120504")
    profile_b = _mf_profile(asset_b)
    _mf_buy_with_detail(scheme_code="120504", nav_date=today - timedelta(days=5))

    provider = MockNavProvider(
        {
            "120503": [NavPoint(today - timedelta(days=4), Decimal("43"), "INR")],
            "120504": [NavPoint(today - timedelta(days=4), Decimal("55"), "INR")],
        },
        fail={"120503"},
    )
    result = sync_mutual_fund_navs(provider=provider)
    assert result.failed == 1
    assert result.synced == 1
    assert HistoricalPrice.objects.filter(asset_symbol="120504").exists()
    assert not HistoricalPrice.objects.filter(asset_symbol="120503").exists()


@pytest.mark.django_db
def test_latest_nav_lookup_reads_db_only(seeded):
    today = date.today()
    asset = _mf_asset(scheme_code="120503")
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=today - timedelta(days=2),
        close_price=Decimal("41.00"),
        currency="INR",
        asset_type=AssetType.MUTUAL_FUND,
        source="amfi",
        asset=asset,
    )
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=today - timedelta(days=1),
        close_price=Decimal("42.00"),
        currency="INR",
        asset_type=AssetType.MUTUAL_FUND,
        source="amfi",
        asset=asset,
    )
    result = latest_nav_for_asset("120503")
    assert result is not None
    assert result.status == "ok"
    assert result.nav == Decimal("42.00")
    assert result.date == today - timedelta(days=1)
    assert result.currency == "INR"

    by_asset = latest_nav_for_asset(asset)
    assert by_asset is not None
    assert by_asset.nav == Decimal("42.00")


@pytest.mark.django_db
def test_latest_nav_missing_returns_nav_missing_status(seeded):
    result = latest_nav_for_asset("999999")
    assert result is not None
    assert result.status == "nav_missing"
    assert result.nav is None


@pytest.mark.django_db
def test_list_mutual_fund_navs_in_range(seeded):
    asset = _mf_asset(scheme_code="120503")
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=date(2026, 1, 1),
        close_price=Decimal("40"),
        currency="INR",
        asset_type=AssetType.MUTUAL_FUND,
        asset=asset,
    )
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=date(2026, 1, 3),
        close_price=Decimal("41"),
        currency="INR",
        asset_type=AssetType.MUTUAL_FUND,
        asset=asset,
    )
    rows = list_mutual_fund_navs_in_range("120503", date(2026, 1, 1), date(2026, 1, 2))
    assert len(rows) == 1
    assert rows[0].close_price == Decimal("40")


@pytest.mark.django_db
def test_stock_latest_price_unaffected_by_mutual_fund_rows(seeded):
    today = date.today()
    HistoricalPrice.objects.create(
        asset_symbol="120503",
        date=today,
        close_price=Decimal("99"),
        currency="INR",
        asset_type=AssetType.MUTUAL_FUND,
    )
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=today,
        close_price=Decimal("150"),
        currency="USD",
        asset_type=AssetType.STOCK,
    )
    stock = latest_historical_price("AAPL")
    assert stock is not None
    assert stock.close_price == Decimal("150")
    assert latest_historical_price("120503") is None


@pytest.mark.django_db
def test_sync_mutual_fund_navs_command(seeded):
    today = date.today()
    _mf_buy_with_detail(scheme_code="120503", nav_date=today - timedelta(days=3))
    provider = MockNavProvider(
        {"120503": [NavPoint(today - timedelta(days=2), Decimal("43"), "INR")]}
    )
    out = StringIO()
    with patch(
        "market_data.management.commands.sync_mutual_fund_navs.sync_mutual_fund_navs",
        return_value=type("R", (), {"synced": 1, "skipped": 0, "failed": 0, "success": True})(),
    ) as mock_sync:
        call_command("sync_mutual_fund_navs", stdout=out)
    mock_sync.assert_called_once()


@pytest.mark.django_db
def test_sync_filters_by_scheme_code(seeded):
    today = date.today()
    _mf_buy_with_detail(scheme_code="120503", nav_date=today - timedelta(days=3))
    _mf_buy_with_detail(scheme_code="120504", nav_date=today - timedelta(days=3))
    provider = MockNavProvider(
        {
            "120503": [NavPoint(today - timedelta(days=2), Decimal("43"), "INR")],
            "120504": [NavPoint(today - timedelta(days=2), Decimal("55"), "INR")],
        }
    )
    result = sync_mutual_fund_navs(provider=provider, only_scheme_codes={"120503"})
    assert result.synced == 1
    called_codes = {c[0] for c in provider.history_calls}
    assert called_codes == {"120503"}
