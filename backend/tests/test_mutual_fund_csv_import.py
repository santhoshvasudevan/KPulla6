"""MF-11a — mutual fund CSV import tests."""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from market_data.models import Asset, AssetType, HistoricalPrice, MutualFundProfile
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Folio, MutualFundTransactionDetail, Transaction, TransactionType


MF_HEADER = (
    "Action,Scheme Code,Scheme Name,Folio Number,Investment Date,NAV Date,"
    "NAV,Units Allotted,Paid Value,Market Value,Fees,Currency\n"
)


def _mf_row(**overrides) -> str:
    base = {
        "action": "BUY",
        "scheme_code": "120503",
        "scheme_name": "Test Direct Growth Fund",
        "folio": "FOLIO-12345",
        "investment_date": "03/10/24",
        "nav_date": "03/15/24",
        "nav": "42.50",
        "units": "100",
        "paid": "4255.00",
        "market": "4250.00",
        "fees": "5.00",
        "currency": "INR",
    }
    base.update(overrides)
    return (
        f"{base['action']},{base['scheme_code']},{base['scheme_name']},{base['folio']},"
        f"{base['investment_date']},{base['nav_date']},{base['nav']},{base['units']},"
        f"{base['paid']},{base['market']},{base['fees']},{base['currency']}\n"
    )


def _import(api_client, csv_text, portfolio_id=None):
    url = "/api/v1/transactions/import-csv"
    if portfolio_id is not None:
        url = f"{url}?portfolio_id={portfolio_id}"
    return api_client.post(
        url,
        {"file": io.BytesIO(csv_text.encode("utf-8"))},
        format="multipart",
    )


def _count_txns():
    return Transaction.objects.count()


def _cached_nav(scheme: str, d: str, close: str):
    HistoricalPrice.objects.create(
        asset_symbol=scheme,
        date=date.fromisoformat(d),
        close_price=Decimal(close),
        currency="INR",
        source="test",
        asset_type=AssetType.MUTUAL_FUND,
    )


@pytest.mark.django_db
def test_mf_csv_import_buy_creates_full_graph(api_client, legacy_seeded):
    csv_text = MF_HEADER + _mf_row()
    response = _import(api_client, csv_text)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["imported_count"] == 1
    assert data["errors"] == []

    txn = Transaction.objects.get(asset_symbol="120503")
    assert txn.type == TransactionType.BUY
    assert txn.date == date(2024, 3, 15)
    assert txn.quantity == Decimal("100")
    assert txn.price_per_share == Decimal("42.50")
    assert txn.currency == "INR"
    assert txn.fees == Decimal("5.00")

    detail = MutualFundTransactionDetail.objects.get(transaction=txn)
    assert detail.investment_date == date(2024, 3, 10)
    assert detail.nav_date == date(2024, 3, 15)
    assert detail.paid_value == Decimal("4255.00")
    assert detail.market_value == Decimal("4250.00")
    assert Asset.objects.filter(asset_type=AssetType.MUTUAL_FUND, symbol="120503").exists()
    assert MutualFundProfile.objects.filter(scheme_code="120503").exists()
    assert Folio.objects.filter(folio_number="FOLIO-12345").exists()


@pytest.mark.django_db
def test_mf_csv_import_sell(api_client, legacy_seeded):
    csv_text = MF_HEADER + _mf_row(action="SELL")
    response = _import(api_client, csv_text)
    assert response.json()["success"] is True
    assert Transaction.objects.get().type == TransactionType.SELL


@pytest.mark.django_db
def test_mf_csv_missing_scheme_code(api_client, legacy_seeded):
    csv_text = MF_HEADER + _mf_row(scheme_code="")
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "Scheme Code" for e in data["errors"])


@pytest.mark.django_db
def test_mf_csv_missing_folio_number(api_client, legacy_seeded):
    csv_text = MF_HEADER + _mf_row(folio="")
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "Folio Number" for e in data["errors"])


@pytest.mark.django_db
def test_mf_csv_invalid_date(api_client, legacy_seeded):
    csv_text = MF_HEADER + _mf_row(nav_date="99/99/24")
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "NAV Date" for e in data["errors"])


@pytest.mark.django_db
def test_mf_csv_invalid_nav(api_client, legacy_seeded):
    csv_text = MF_HEADER + _mf_row(nav="0")
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any("NAV" in e["field"] or "nav" in e["message"].lower() for e in data["errors"])


@pytest.mark.django_db
def test_mf_csv_invalid_units(api_client, legacy_seeded):
    csv_text = MF_HEADER + _mf_row(units="-1")
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any("Units Allotted" in e["field"] for e in data["errors"])


@pytest.mark.django_db
def test_mf_csv_invalid_paid_value(api_client, legacy_seeded):
    csv_text = MF_HEADER + _mf_row(paid="-1")
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any("Paid Value" in e["field"] for e in data["errors"])


@pytest.mark.django_db
def test_mf_csv_omitted_fees_uses_default(api_client, legacy_seeded):
    row = _mf_row(fees="").replace(",5.00,", ",,")
    csv_text = MF_HEADER + row
    response = _import(api_client, csv_text)
    assert response.json()["success"] is True
    assert Transaction.objects.get().fees == Decimal("5.00")


@pytest.mark.django_db
def test_mf_csv_assigns_portfolio_id(api_client, legacy_seeded, test_user):
    target = Portfolio.objects.create(user=test_user, name="MF Target", base_currency="INR", is_active=True)
    csv_text = MF_HEADER + _mf_row()
    response = _import(api_client, csv_text, portfolio_id=target.id)
    assert response.json()["success"] is True
    assert Transaction.objects.get().portfolio_id == target.id


@pytest.mark.django_db
def test_mf_csv_rejects_unknown_portfolio_id(api_client, legacy_seeded):
    csv_text = MF_HEADER + _mf_row()
    response = _import(api_client, csv_text, portfolio_id=999999)
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.django_db
def test_mf_csv_rejects_inactive_portfolio_id(api_client, legacy_seeded, test_user):
    inactive = Portfolio.objects.create(user=test_user, name="Inactive MF", is_active=False)
    csv_text = MF_HEADER + _mf_row()
    response = _import(api_client, csv_text, portfolio_id=inactive.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_mf_csv_all_or_nothing(api_client, legacy_seeded):
    before = _count_txns()
    csv_text = MF_HEADER + _mf_row() + _mf_row(units="-1")
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert data["imported_count"] == 0
    assert _count_txns() == before


@pytest.mark.django_db
def test_mf_csv_nav_verification_uses_cached_db_only(api_client, legacy_seeded):
    _cached_nav("120503", "2024-03-15", "42.500000")
    csv_text = MF_HEADER + _mf_row()
    with patch(
        "market_data.providers.mutual_fund_nav_provider.AmfiNavProvider.get_latest_nav"
    ) as mock_latest:
        response = _import(api_client, csv_text)
        mock_latest.assert_not_called()
    assert response.json()["success"] is True
    detail = MutualFundTransactionDetail.objects.get()
    assert detail.nav_verification_status == "VERIFIED"


@pytest.mark.django_db
def test_mf_csv_rejects_mixed_stock_and_mf_headers(api_client, legacy_seeded):
    csv_text = (
        "Action,Date,ASSET SYMBOL,Qty,Price/Share,Scheme Code,Folio Number\n"
        "Buy,01/15/24,AAPL,10,150.00,120503,FOLIO-1\n"
    )
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any("Mixed stock and mutual fund" in e["message"] for e in data["errors"])


@pytest.mark.django_db
def test_mf_csv_rejects_invalid_action(api_client, legacy_seeded):
    csv_text = MF_HEADER + _mf_row(action="DIVIDEND")
    data = _import(api_client, csv_text).json()
    assert data["success"] is False
    assert any(e["field"] == "Action" for e in data["errors"])
