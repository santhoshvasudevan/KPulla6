from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from fx.lookup import convert_amount_on_date, get_fx_rate_on_date
from fx.models import FXRate
from fx.providers.base import DailyFxRate
from fx.services import sync_fx_rates, upsert_fx_rate


class MockFxProvider:
    def __init__(self, data: dict[tuple[str, str], list[DailyFxRate]] | None = None):
        self.data = data or {}

    def fetch_rates(self, from_currency: str, to_currency: str, start: date, end: date):
        return [
            r
            for r in self.data.get((from_currency, to_currency), [])
            if start <= r.date <= end
        ]


@pytest.mark.django_db
def test_fx_upsert_idempotent():
    d = date(2026, 1, 1)
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d, rate=Decimal("0.9"))
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d, rate=Decimal("0.91"))
    assert FXRate.objects.filter(from_currency="USD", to_currency="EUR", date=d).count() == 1
    assert FXRate.objects.get(from_currency="USD", to_currency="EUR", date=d).rate == Decimal(
        "0.91"
    )


@pytest.mark.django_db
def test_fx_unique_pair_date():
    d = date(2026, 1, 2)
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d, rate=Decimal("1"))
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d, rate=Decimal("2"))
    assert FXRate.objects.filter(from_currency="USD", to_currency="EUR").count() == 1


@pytest.mark.django_db
def test_same_date_fx_lookup():
    d = date(2026, 2, 1)
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d, rate=Decimal("0.85"))
    rate = get_fx_rate_on_date("USD", "EUR", d)
    assert rate == Decimal("0.85")
    amount, status = convert_amount_on_date(100, "USD", "EUR", d)
    assert status == "ok"
    assert amount == Decimal("85")


@pytest.mark.django_db
def test_missing_fx_lookup_returns_none():
    d = date(2026, 3, 1)
    assert get_fx_rate_on_date("USD", "INR", d) is None
    amount, status = convert_amount_on_date(10, "USD", "INR", d)
    assert amount is None
    assert status == "fx_unavailable"


@pytest.mark.django_db
def test_no_latest_fx_fallback_for_historical_date():
    d1 = date(2026, 1, 1)
    d2 = date(2026, 1, 10)
    upsert_fx_rate(from_currency="USD", to_currency="EUR", row_date=d2, rate=Decimal("0.99"))
    assert get_fx_rate_on_date("USD", "EUR", d1) is None


@pytest.mark.django_db
def test_sync_fx_rates_command_calls_service():
    with patch("fx.management.commands.sync_fx_rates.sync_fx_rates") as m:
        m.return_value = type(
            "R", (), {"success": True, "partial": False, "pairs_attempted": 0}
        )()
        call_command("sync_fx_rates", stdout=StringIO())
    m.assert_called_once()


@pytest.mark.django_db
def test_sync_fx_rates_incremental(seeded):
    from portfolios.seed import ensure_default_portfolio
    from transactions.models import Transaction, TransactionType

    today = date.today()
    portfolio = ensure_default_portfolio()
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="AAPL",
        date=today - timedelta(days=5),
        type=TransactionType.BUY,
        quantity=Decimal("1"),
        price_per_share=Decimal("100"),
        currency="EUR",
        fees=Decimal("0"),
    )
    provider = MockFxProvider(
        {
            ("USD", "EUR"): [
                DailyFxRate(today - timedelta(days=1), Decimal("0.9")),
            ]
        }
    )
    result = sync_fx_rates(pairs={("USD", "EUR")}, provider=provider)
    assert result.success is True
    assert FXRate.objects.filter(from_currency="USD", to_currency="EUR").exists()
