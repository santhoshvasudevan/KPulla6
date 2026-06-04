"""MF-1 schema foundation — model tests for Indian Mutual Funds."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from market_data.models import (
    Asset,
    AssetType,
    HistoricalPrice,
    MutualFundProfile,
    PrimaryAssetClass,
)
from portfolios.seed import ensure_default_portfolio
from transactions.models import (
    Folio,
    MutualFundTransactionDetail,
    NavVerificationStatus,
    Transaction,
    TransactionType,
)


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
        "fund_house": "Test AMC",
        "scheme_category": "Equity Scheme - Large Cap Fund",
        "direct_or_regular": "Direct",
        "growth_or_idcw": "Growth",
    }
    defaults.update(kwargs)
    return MutualFundProfile.objects.create(**defaults)


def _folio(*, portfolio, asset: Asset, folio_number: str = "1234567890") -> Folio:
    return Folio.objects.create(
        portfolio=portfolio,
        asset=asset,
        folio_number=folio_number,
    )


@pytest.mark.django_db
def test_asset_creation_mutual_fund():
    asset = _mf_asset(scheme_code="120503")
    assert asset.id is not None
    assert asset.asset_type == AssetType.MUTUAL_FUND
    assert asset.symbol == "120503"
    assert asset.currency == "INR"
    assert asset.provider == "amfi"
    assert asset.primary_asset_class == PrimaryAssetClass.EQUITY
    assert asset.region == "IN"
    assert asset.is_active is True


@pytest.mark.django_db
def test_asset_unique_per_type_and_symbol():
    _mf_asset(scheme_code="120503")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _mf_asset(scheme_code="120503")


@pytest.mark.django_db
def test_asset_stock_and_mutual_fund_same_symbol_allowed():
    """STOCK and MUTUAL_FUND may share symbol string under (asset_type, symbol) uniqueness."""
    Asset.objects.create(
        asset_type=AssetType.STOCK,
        symbol="120503",
        display_name="Legacy ticker",
        currency="USD",
        provider="yfinance",
        region="US",
    )
    mf = _mf_asset(scheme_code="120503")
    assert mf.asset_type == AssetType.MUTUAL_FUND


@pytest.mark.django_db
def test_mutual_fund_profile_scheme_code_unique():
    asset = _mf_asset(scheme_code="120503")
    _mf_profile(asset)
    asset2 = _mf_asset(scheme_code="120504")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MutualFundProfile.objects.create(
                asset=asset2,
                scheme_code="120503",
                scheme_name="Duplicate code profile",
            )


@pytest.mark.django_db
def test_mutual_fund_profile_links_to_asset():
    asset = _mf_asset(scheme_code="125497")
    profile = _mf_profile(
        asset,
        scheme_name="Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
        isin_growth="INF879O01027",
    )
    assert profile.scheme_code == "125497"
    assert profile.asset_id == asset.id
    assert asset.mutual_fund_profile.scheme_name.startswith("Parag Parikh")


@pytest.mark.django_db
def test_folio_uniqueness_per_portfolio_asset_and_number(test_user):
    portfolio = ensure_default_portfolio(test_user)
    asset = _mf_asset(scheme_code="120503")
    _folio(portfolio=portfolio, asset=asset, folio_number="FOLIO-001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _folio(portfolio=portfolio, asset=asset, folio_number="FOLIO-001")


@pytest.mark.django_db
def test_folio_same_number_different_assets_allowed(test_user):
    portfolio = ensure_default_portfolio(test_user)
    asset_a = _mf_asset(scheme_code="120503")
    asset_b = _mf_asset(scheme_code="120504")
    _folio(portfolio=portfolio, asset=asset_a, folio_number="SHARED-NUM")
    folio_b = _folio(portfolio=portfolio, asset=asset_b, folio_number="SHARED-NUM")
    assert folio_b.folio_number == "SHARED-NUM"


@pytest.mark.django_db
def test_folio_required_for_mutual_fund_transaction_detail(test_user):
    """MF transaction detail must reference a Folio row (folio required concept)."""
    portfolio = ensure_default_portfolio(test_user)
    asset = _mf_asset(scheme_code="120503")
    folio = _folio(portfolio=portfolio, asset=asset)
    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol=asset.symbol,
        date=date(2026, 3, 15),
        type=TransactionType.BUY,
        quantity=Decimal("100.00000000"),
        price_per_share=Decimal("42.500000"),
        currency="INR",
    )
    detail = MutualFundTransactionDetail.objects.create(
        transaction=txn,
        folio=folio,
        investment_date=date(2026, 3, 14),
        nav_date=date(2026, 3, 15),
        nav=Decimal("42.500000"),
        units_allotted=Decimal("100.00000000"),
        paid_value=Decimal("4255.00"),
        market_value=Decimal("4250.00"),
    )
    assert detail.folio_id == folio.id
    assert detail.nav_verification_status == NavVerificationStatus.NOT_VERIFIED


@pytest.mark.django_db
def test_mutual_fund_transaction_detail_dates_and_amounts(test_user):
    portfolio = ensure_default_portfolio(test_user)
    asset = _mf_asset(scheme_code="120503")
    folio = _folio(portfolio=portfolio, asset=asset)
    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol=asset.symbol,
        date=date(2026, 3, 15),
        type=TransactionType.BUY,
        quantity=Decimal("50.5"),
        price_per_share=Decimal("10.25"),
        currency="INR",
    )
    detail = MutualFundTransactionDetail.objects.create(
        transaction=txn,
        folio=folio,
        investment_date=date(2026, 3, 10),
        nav_date=date(2026, 3, 15),
        nav=Decimal("10.25"),
        units_allotted=Decimal("50.5"),
        paid_value=Decimal("518.00"),
        market_value=Decimal("517.625"),
        nav_verification_status=NavVerificationStatus.WARNING,
        nav_verification_message="NAV differs from cache by 1.2%",
    )
    assert detail.investment_date != detail.nav_date
    assert detail.investment_date == date(2026, 3, 10)
    assert detail.nav_date == date(2026, 3, 15)
    assert detail.nav == Decimal("10.25")
    assert detail.units_allotted == Decimal("50.5")
    assert detail.paid_value == Decimal("518.00")
    assert detail.market_value == Decimal("517.625")
    assert detail.nav_verification_status == NavVerificationStatus.WARNING


@pytest.mark.django_db
def test_mutual_fund_transaction_detail_one_to_one(test_user):
    portfolio = ensure_default_portfolio(test_user)
    asset = _mf_asset(scheme_code="120503")
    folio = _folio(portfolio=portfolio, asset=asset)
    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol=asset.symbol,
        date=date(2026, 4, 1),
        type=TransactionType.BUY,
        quantity=Decimal("1"),
        price_per_share=Decimal("100"),
        currency="INR",
    )
    MutualFundTransactionDetail.objects.create(
        transaction=txn,
        folio=folio,
        investment_date=date(2026, 4, 1),
        nav_date=date(2026, 4, 1),
        nav=Decimal("100"),
        units_allotted=Decimal("1"),
        paid_value=Decimal("100"),
        market_value=Decimal("100"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MutualFundTransactionDetail.objects.create(
                transaction=txn,
                folio=folio,
                investment_date=date(2026, 4, 1),
                nav_date=date(2026, 4, 1),
                nav=Decimal("100"),
                units_allotted=Decimal("1"),
                paid_value=Decimal("100"),
                market_value=Decimal("100"),
            )


@pytest.mark.django_db
def test_historical_price_asset_fk_nullable_and_stock_uniqueness_unchanged():
    """Existing (asset_symbol, date) uniqueness and stock rows remain valid."""
    HistoricalPrice.objects.create(
        asset_symbol="AAPL",
        date=date(2026, 1, 1),
        close_price=Decimal("150.00"),
        currency="USD",
        asset_type=AssetType.STOCK,
        asset=None,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            HistoricalPrice.objects.create(
                asset_symbol="AAPL",
                date=date(2026, 1, 1),
                close_price=Decimal("151.00"),
                currency="USD",
                asset_type=AssetType.STOCK,
            )


@pytest.mark.django_db
def test_historical_price_mutual_fund_type_and_optional_asset_fk():
    asset = _mf_asset(scheme_code="120503")
    hp = HistoricalPrice.objects.create(
        asset_symbol=asset.symbol,
        date=date(2026, 3, 15),
        close_price=Decimal("42.50"),
        currency="INR",
        asset_type=AssetType.MUTUAL_FUND,
        source="amfi",
        asset=asset,
    )
    assert hp.asset_id == asset.id
    assert hp.asset_type == AssetType.MUTUAL_FUND
