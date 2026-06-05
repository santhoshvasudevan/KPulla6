"""Cash-7B — legacy cash backfill apply API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from cash.backfill_apply import _format_backfill_note
from cash.models import CashEntryType, CashLedgerEntry
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction, TransactionType

URL = "/api/v1/cash/backfill-apply"
PREVIEW_URL = "/api/v1/cash/backfill-preview"


def _legacy(portfolio: Portfolio) -> Portfolio:
    if portfolio.cash_aware_enabled:
        portfolio.cash_aware_enabled = False
        portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    return portfolio


def _enable_cash_aware(portfolio: Portfolio) -> Portfolio:
    portfolio.cash_aware_enabled = True
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


def _buy(api_client, portfolio_id: int, **kwargs):
    payload = {
        "asset_symbol": "AAPL",
        "date": "2026-01-01",
        "type": "BUY",
        "quantity": "10",
        "price_per_share": "100",
        "currency": "EUR",
        "fees": "0",
        "portfolio_id": portfolio_id,
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _sell(api_client, portfolio_id: int, **kwargs):
    payload = {
        "asset_symbol": "AAPL",
        "date": "2026-02-01",
        "type": "SELL",
        "quantity": "10",
        "price_per_share": "150",
        "currency": "EUR",
        "fees": "0",
        "portfolio_id": portfolio_id,
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _mf_buy(api_client, portfolio_id: int, **kwargs):
    payload = {
        "asset_type": "MUTUAL_FUND",
        "scheme_code": "120503",
        "scheme_name": "Test Fund",
        "folio_number": "F1",
        "type": "BUY",
        "investment_date": "2026-03-10",
        "nav_date": "2026-03-15",
        "nav": "42.5",
        "units_allotted": "100",
        "paid_value": "4255.00",
        "market_value": "4250.00",
        "currency": "INR",
        "portfolio_id": portfolio_id,
    }
    payload.update(kwargs)
    return api_client.post("/api/v1/transactions", payload, format="json")


def _apply(api_client, portfolio_id: int, **body):
    payload = {
        "portfolio_id": portfolio_id,
        "mode": "shortfall",
        "confirmed": True,
    }
    payload.update(body)
    return api_client.post(URL, payload, format="json")


@pytest.mark.django_db
def test_apply_requires_confirmed_true(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(api_client, portfolio.id, date="2026-01-01")
    for confirmed in (False, None):
        payload = {"portfolio_id": portfolio.id, "mode": "shortfall"}
        if confirmed is not None:
            payload["confirmed"] = confirmed
        response = api_client.post(URL, payload, format="json")
        assert response.status_code == 400
        assert "explicit confirmation" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_apply_legacy_stock_creates_cash_deposits(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(api_client, portfolio.id, date="2026-01-01", quantity="10", price_per_share="100")
    before = CashLedgerEntry.objects.filter(portfolio=portfolio).count()
    response = _apply(api_client, portfolio.id)
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 1
    assert data["skipped_existing_count"] == 0
    assert len(data["created_deposits"]) == 1
    dep = data["created_deposits"][0]
    assert dep["entry_type"] == "CASH_DEPOSIT"
    assert dep["currency"] == "EUR"
    assert dep["amount"] == 1000.0
    assert dep["source_of_funds"] == "Backfill deposit"
    assert dep["note"].startswith("Backfill:")
    assert "BUY AAPL" in dep["note"]
    assert CashLedgerEntry.objects.filter(portfolio=portfolio).count() == before + 1
    entry = CashLedgerEntry.objects.get(pk=dep["id"])
    assert entry.linked_transaction_id is None
    assert entry.transfer_group_id is None


@pytest.mark.django_db
def test_apply_recomputes_preview_ignores_frontend_deposits(
    api_client, seeded, test_user
):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(api_client, portfolio.id, date="2026-01-01")
    response = _apply(
        api_client,
        portfolio.id,
        proposed_deposits=[
            {
                "date": "2026-01-01",
                "currency": "EUR",
                "amount": 1.0,
                "source_of_funds": "Backfill deposit",
                "note": "fake",
            }
        ],
    )
    assert response.status_code == 200
    assert response.json()["created_deposits"][0]["amount"] == 1000.0


@pytest.mark.django_db
def test_apply_is_atomic(seeded, test_user):
    from cash.backfill_apply import apply_cash_backfill

    portfolio = _legacy(ensure_default_portfolio(test_user))
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="AAA",
        date=date(2026, 1, 1),
        type=TransactionType.BUY,
        quantity=Decimal("10"),
        price_per_share=Decimal("100"),
        currency="EUR",
        fees=Decimal("0"),
    )
    Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="BBB",
        date=date(2026, 1, 2),
        type=TransactionType.BUY,
        quantity=Decimal("5"),
        price_per_share=Decimal("200"),
        currency="EUR",
        fees=Decimal("0"),
    )
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
            apply_cash_backfill(portfolio)
    assert CashLedgerEntry.objects.filter(portfolio=portfolio).count() == before


@pytest.mark.django_db
def test_apply_does_not_enable_cash_aware(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(api_client, portfolio.id, date="2026-01-01")
    response = _apply(api_client, portfolio.id)
    assert response.status_code == 200
    data = response.json()
    assert data["cash_aware_enabled"] is False
    assert data["cash_aware_enablement"]["enabled"] is False
    assert "separately" in data["cash_aware_enablement"]["message"].lower()
    portfolio.refresh_from_db()
    assert portfolio.cash_aware_enabled is False


@pytest.mark.django_db
def test_apply_no_proposals_returns_zero_created(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-01-01", amount="10000")
    _buy(api_client, portfolio.id, date="2026-01-01")
    response = _apply(api_client, portfolio.id)
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert data["skipped_existing_count"] == 0
    assert data["created_deposits"] == []


@pytest.mark.django_db
def test_apply_skips_duplicate_identical_deposits(seeded, test_user):
    from cash.backfill_apply import apply_cash_backfill
    from cash.backfill_preview import (
        BackfillPreviewResult,
        BackfillPreviewSummary,
        BackfillProposedDeposit,
    )

    portfolio = _legacy(ensure_default_portfolio(test_user))
    note = _format_backfill_note("Proposed before historical BUY AAPL")
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 1, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("1000.0000"),
        source_of_funds="Backfill deposit",
        note=note,
    )
    preview_result = BackfillPreviewResult(
        portfolio=portfolio,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 4),
        mode="shortfall",
        can_enable_cash_aware_after_apply=False,
        summary=BackfillPreviewSummary(proposed_deposit_count=1),
        proposed_deposits=[
            BackfillProposedDeposit(
                portfolio_id=portfolio.id,
                date=date(2026, 1, 1),
                currency="EUR",
                amount=Decimal("1000"),
                note="Proposed before historical BUY AAPL",
            )
        ],
    )
    with patch(
        "cash.backfill_apply.simulate_cash_backfill_preview",
        return_value=preview_result,
    ):
        result = apply_cash_backfill(portfolio)
    assert result.created_count == 0
    assert result.skipped_existing_count == 1


@pytest.mark.django_db
def test_apply_second_call_no_extra_rows_when_ledger_covers_shortfall(
    api_client, seeded, test_user
):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(api_client, portfolio.id, date="2026-01-01")
    first = _apply(api_client, portfolio.id)
    assert first.status_code == 200
    assert first.json()["created_count"] == 1
    count_after_first = CashLedgerEntry.objects.filter(portfolio=portfolio).count()
    second = _apply(api_client, portfolio.id)
    assert second.status_code == 200
    assert second.json()["created_count"] == 0
    assert (
        CashLedgerEntry.objects.filter(portfolio=portfolio).count()
        == count_after_first
    )


@pytest.mark.django_db
def test_apply_mf_inr_paid_value_investment_date(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _mf_buy(api_client, portfolio.id)
    response = _apply(
        api_client,
        portfolio.id,
        start_date="2026-03-01",
        end_date="2026-03-31",
    )
    assert response.status_code == 200
    dep = response.json()["created_deposits"][0]
    assert dep["currency"] == "INR"
    assert dep["amount"] == 4255.0
    assert dep["date"] == "2026-03-10"


@pytest.mark.django_db
def test_apply_usd_does_not_fund_eur_buy(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _deposit(portfolio, day="2026-01-01", amount="5000", currency="USD")
    _buy(api_client, portfolio.id, date="2026-01-02", currency="EUR")
    response = _apply(api_client, portfolio.id)
    assert response.status_code == 200
    dep = response.json()["created_deposits"][0]
    assert dep["currency"] == "EUR"
    assert dep["amount"] == 1000.0


@pytest.mark.django_db
def test_apply_does_not_create_settlement_rows(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(api_client, portfolio.id, date="2026-01-01")
    _apply(api_client, portfolio.id)
    settlement_types = {CashEntryType.BUY_SETTLEMENT, CashEntryType.SELL_SETTLEMENT}
    assert not CashLedgerEntry.objects.filter(
        portfolio=portfolio, entry_type__in=settlement_types
    ).exists()


@pytest.mark.django_db
def test_apply_does_not_mutate_transactions(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(api_client, portfolio.id, date="2026-01-01")
    before = list(
        Transaction.objects.filter(portfolio=portfolio).values(
            "id", "type", "quantity", "price_per_share", "currency", "date"
        )
    )
    _apply(api_client, portfolio.id)
    after = list(
        Transaction.objects.filter(portfolio=portfolio).values(
            "id", "type", "quantity", "price_per_share", "currency", "date"
        )
    )
    assert before == after


@pytest.mark.django_db
def test_apply_unknown_portfolio_404(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    response = _apply(api_client, portfolio.id + 99999)
    assert response.status_code == 404


@pytest.mark.django_db
def test_apply_inactive_portfolio_404(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    portfolio.is_active = False
    portfolio.save(update_fields=["is_active", "updated_at"])
    response = _apply(api_client, portfolio.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_apply_invalid_date_range_400(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    response = _apply(
        api_client,
        portfolio.id,
        start_date="2026-06-01",
        end_date="2026-01-01",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_apply_matches_preview_amounts(api_client, seeded, test_user):
    portfolio = _legacy(ensure_default_portfolio(test_user))
    _buy(api_client, portfolio.id, date="2026-01-01")
    preview = api_client.post(
        PREVIEW_URL,
        {"portfolio_id": portfolio.id, "mode": "shortfall"},
        format="json",
    ).json()
    apply_data = _apply(api_client, portfolio.id).json()
    assert preview["proposed_deposits"][0]["amount"] == apply_data["created_deposits"][0][
        "amount"
    ]


@pytest.mark.django_db
def test_format_backfill_note_prefix():
    assert _format_backfill_note("Proposed before BUY").startswith("Backfill:")
    assert _format_backfill_note("Backfill: already").startswith("Backfill:")
