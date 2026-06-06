"""Cash-7D — bulk manual cash deposit/withdrawal schedule API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from cash.bulk_entries import apply_bulk_cash_entries, preview_bulk_cash_entries
from cash.models import CashEntryType, CashLedgerEntry
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction

PREVIEW_URL = "/api/v1/cash/bulk-entries/preview"
APPLY_URL = "/api/v1/cash/bulk-entries/apply"


def _legacy(portfolio: Portfolio) -> Portfolio:
    if portfolio.cash_aware_enabled:
        portfolio.cash_aware_enabled = False
        portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


def _deposit(portfolio: Portfolio, *, day: str, amount: str, currency: str = "EUR"):
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date.fromisoformat(day),
        currency=currency,
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
    )


def _preview(api_client, portfolio_id: int, **body):
    payload = {
        "portfolio_id": portfolio_id,
        "entry_type": "CASH_DEPOSIT",
        "currency": "EUR",
        "amount": "900",
        "start_date": "2022-06-01",
        "end_date": "2022-12-01",
        "frequency": "monthly",
        "source_of_funds": "Monthly contribution",
        "note": "Historical contribution",
    }
    payload.update(body)
    return api_client.post(PREVIEW_URL, payload, format="json")


def _apply(api_client, portfolio_id: int, **body):
    payload = {
        "portfolio_id": portfolio_id,
        "entry_type": "CASH_DEPOSIT",
        "currency": "EUR",
        "amount": "900",
        "start_date": "2022-06-01",
        "end_date": "2022-12-01",
        "frequency": "monthly",
        "source_of_funds": "Monthly contribution",
        "note": "Historical contribution",
        "confirmed": True,
    }
    payload.update(body)
    return api_client.post(APPLY_URL, payload, format="json")


@pytest.mark.django_db
def test_preview_monthly_schedule_dates_and_count(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    data = _preview(api_client, portfolio.id).json()
    assert data["entry_count"] == 7
    assert len(data["entries"]) == 7
    assert data["entries"][0]["date"] == "2022-06-01"
    assert data["entries"][-1]["date"] == "2022-12-01"
    assert data["entries"][0]["amount"] == 900.0
    assert data["entries"][0]["entry_type"] == "CASH_DEPOSIT"
    assert data["total_by_currency"] == [{"currency": "EUR", "amount": 6300.0}]


@pytest.mark.django_db
def test_preview_once_single_entry(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    data = _preview(
        api_client,
        portfolio.id,
        start_date="2022-05-01",
        frequency="once",
        amount="12500",
        end_date=None,
    ).json()
    assert data["entry_count"] == 1
    assert data["entries"][0]["date"] == "2022-05-01"
    assert data["entries"][0]["amount"] == 12500.0


@pytest.mark.django_db
def test_apply_requires_confirmed_true(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    for confirmed in (False, None):
        payload = {
            "portfolio_id": portfolio.id,
            "entry_type": "CASH_DEPOSIT",
            "currency": "EUR",
            "amount": "900",
            "start_date": "2022-06-01",
            "end_date": "2022-12-01",
            "frequency": "monthly",
        }
        if confirmed is not None:
            payload["confirmed"] = confirmed
        response = api_client.post(APPLY_URL, payload, format="json")
        assert response.status_code == 400
        assert "explicit confirmation" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_apply_creates_deposits_atomically(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    before = CashLedgerEntry.objects.filter(portfolio=portfolio).count()
    response = _apply(api_client, portfolio.id)
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 7
    assert data["skipped_existing_count"] == 0
    assert len(data["created_entries"]) == 7
    assert CashLedgerEntry.objects.filter(portfolio=portfolio).count() == before + 7
    assert not CashLedgerEntry.objects.filter(
        portfolio=portfolio, entry_type=CashEntryType.BUY_SETTLEMENT
    ).exists()


@pytest.mark.django_db
def test_apply_is_atomic(seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    before = CashLedgerEntry.objects.filter(portfolio=portfolio).count()
    call_count = {"n": 0}
    original_save = CashLedgerEntry.save

    def flaky_save(self, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated failure")
        return original_save(self, *args, **kwargs)

    with patch.object(CashLedgerEntry, "save", flaky_save):
        with pytest.raises(RuntimeError):
            apply_bulk_cash_entries(
                portfolio,
                entry_type=CashEntryType.CASH_DEPOSIT,
                currency="EUR",
                amount=Decimal("100"),
                start_date=date(2022, 1, 1),
                end_date=date(2022, 3, 1),
                frequency="monthly",
            )
    assert CashLedgerEntry.objects.filter(portfolio=portfolio).count() == before


@pytest.mark.django_db
def test_apply_skips_duplicate_identical_entries(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    first = _apply(api_client, portfolio.id)
    assert first.status_code == 200
    assert first.json()["created_count"] == 7
    second = _apply(api_client, portfolio.id)
    assert second.status_code == 200
    data = second.json()
    assert data["created_count"] == 0
    assert data["skipped_existing_count"] == 7


@pytest.mark.django_db
def test_withdrawal_schedule_blocked_when_future_negative(
    api_client, seeded, test_user
):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2022-06-01", amount="500")
    response = _apply(
        api_client,
        portfolio.id,
        entry_type="CASH_WITHDRAWAL",
        amount="900",
        start_date="2022-06-01",
        end_date="2022-07-01",
        frequency="monthly",
        source_of_funds="",
        note="Withdrawal",
    )
    assert response.status_code == 400
    assert "negative" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_preview_withdrawal_warning(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2022-06-01", amount="500")
    data = _preview(
        api_client,
        portfolio.id,
        entry_type="CASH_WITHDRAWAL",
        amount="900",
        start_date="2022-06-01",
        end_date="2022-07-01",
        frequency="monthly",
    ).json()
    assert any("negative" in w.lower() for w in data["warnings"])


@pytest.mark.django_db
def test_unknown_portfolio_404(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    assert _preview(api_client, portfolio.id + 99999).status_code == 404


@pytest.mark.django_db
def test_inactive_portfolio_404(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    portfolio.is_active = False
    portfolio.save(update_fields=["is_active", "updated_at"])
    assert _apply(api_client, portfolio.id).status_code == 404


@pytest.mark.django_db
def test_invalid_date_range_400(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    response = _preview(
        api_client,
        portfolio.id,
        start_date="2022-12-01",
        end_date="2022-06-01",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_unsupported_currency_400(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    response = _preview(api_client, portfolio.id, currency="XXX")
    assert response.status_code == 400


@pytest.mark.django_db
def test_apply_does_not_mutate_transactions(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="AAA",
        date=date(2022, 6, 1),
        type="BUY",
        quantity=Decimal("1"),
        price_per_share=Decimal("100"),
        currency="EUR",
        fees=Decimal("0"),
    )
    before = Transaction.objects.filter(portfolio=portfolio).count()
    _apply(api_client, portfolio.id)
    assert Transaction.objects.filter(portfolio=portfolio).count() == before


@pytest.mark.django_db
def test_apply_recomputes_schedule_ignores_frontend_entries(
    api_client, seeded, test_user
):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    response = api_client.post(
        APPLY_URL,
        {
            "portfolio_id": portfolio.id,
            "entry_type": "CASH_DEPOSIT",
            "currency": "EUR",
            "amount": "900",
            "start_date": "2022-06-01",
            "end_date": "2022-06-01",
            "frequency": "monthly",
            "confirmed": True,
            "entries": [{"date": "2099-01-01", "amount": 1}],
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["created_count"] == 1
    entry = response.json()["created_entries"][0]
    assert entry["date"] == "2022-06-01"
    assert entry["amount"] == 900.0


@pytest.mark.django_db
def test_monthly_requires_end_date(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    response = _preview(
        api_client,
        portfolio.id,
        frequency="monthly",
        end_date=None,
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_preview_duplicate_warning(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2022, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("900"),
        source_of_funds="Monthly contribution",
        note="Historical contribution",
    )
    data = _preview(api_client, portfolio.id).json()
    assert data["duplicate_count"] == 1
    assert any("skipped" in w.lower() for w in data["warnings"])
