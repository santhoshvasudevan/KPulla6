from datetime import date
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from transactions.models import Transaction

LEDGER_ITEM_KEYS = {
    "id",
    "portfolio_id",
    "portfolio_name",
    "date",
    "currency",
    "entry_type",
    "amount",
    "source_of_funds",
    "linked_transaction_id",
    "transfer_group_id",
    "note",
    "created_at",
    "updated_at",
}


def _post_deposit(api_client, portfolio_id, **overrides):
    payload = {
        "portfolio_id": portfolio_id,
        "date": "2026-06-04",
        "currency": "EUR",
        "amount": "1000.00",
        "source_of_funds": "Bank transfer",
        "note": "Monthly contribution",
    }
    payload.update(overrides)
    return api_client.post("/api/v1/cash/deposits", payload, format="json")


def _post_withdrawal(api_client, portfolio_id, **overrides):
    payload = {
        "portfolio_id": portfolio_id,
        "date": "2026-06-04",
        "currency": "EUR",
        "amount": "500.00",
        "note": "Withdrawal to bank",
    }
    payload.update(overrides)
    return api_client.post("/api/v1/cash/withdrawals", payload, format="json")


def _deposit(portfolio, *, day: str, amount: str, currency: str = "EUR", note: str = ""):
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date.fromisoformat(day),
        currency=currency,
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
        note=note,
    )


@pytest.mark.django_db
def test_unauthenticated_cash_balances_returns_401_or_403(anon_client):
    response = anon_client.get("/api/v1/cash/balances")
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_unauthenticated_cash_ledger_returns_401_or_403(anon_client):
    response = anon_client.get("/api/v1/cash/ledger")
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_balances_empty_when_no_ledger_entries(api_client, seeded, test_user):
    response = api_client.get("/api/v1/cash/balances")
    assert response.status_code == 200
    data = response.json()
    assert data["portfolio_scope"] == "all"
    assert data["balances"] == []
    assert data["totals_by_currency"] == []


@pytest.mark.django_db
def test_balances_group_by_portfolio_and_currency(api_client, seeded, test_user):
    default = ensure_default_portfolio(test_user)
    second = Portfolio.objects.create(
        user=test_user, name="IndianMF", base_currency="INR", is_active=True
    )
    _deposit(default, day="2022-05-01", amount="12500")
    _deposit(second, day="2023-01-20", amount="50000", currency="INR")

    response = api_client.get("/api/v1/cash/balances")
    assert response.status_code == 200
    data = response.json()
    assert len(data["balances"]) == 2
    by_key = {(b["portfolio_id"], b["currency"]): b["balance"] for b in data["balances"]}
    assert by_key[(default.id, "EUR")] == 12500.0
    assert by_key[(second.id, "INR")] == 50000.0
    totals = {t["currency"]: t["balance"] for t in data["totals_by_currency"]}
    assert totals["EUR"] == 12500.0
    assert totals["INR"] == 50000.0


@pytest.mark.django_db
def test_balances_as_of_date_filters(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _deposit(portfolio, day="2026-01-01", amount="1000")
    _deposit(portfolio, day="2026-06-01", amount="500")

    response = api_client.get(
        "/api/v1/cash/balances",
        {"portfolio_id": portfolio.id, "as_of_date": "2026-01-15"},
    )
    assert response.status_code == 200
    assert response.json()["balances"] == [{"currency": "EUR", "balance": 1000.0}]


@pytest.mark.django_db
def test_balances_single_portfolio_scope(api_client, seeded, test_user):
    default = ensure_default_portfolio(test_user)
    other = Portfolio.objects.create(
        user=test_user, name="Other", base_currency="EUR", is_active=True
    )
    _deposit(default, day="2026-01-01", amount="100")
    _deposit(other, day="2026-01-01", amount="999")

    response = api_client.get(
        "/api/v1/cash/balances", {"portfolio_id": default.id}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["portfolio_id"] == default.id
    assert data["balances"] == [{"currency": "EUR", "balance": 100.0}]
    assert "portfolio_scope" not in data


@pytest.mark.django_db
def test_balances_scope_all_and_portfolio_id_422(api_client, seeded):
    response = api_client.get(
        "/api/v1/cash/balances",
        {"portfolio_scope": "all", "portfolio_id": 1},
    )
    assert response.status_code == 422


@pytest.mark.django_db
def test_balances_unknown_portfolio_404(api_client, seeded):
    response = api_client.get("/api/v1/cash/balances", {"portfolio_id": 999999})
    assert response.status_code == 404


@pytest.mark.django_db
def test_balances_not_owned_portfolio_404(api_client, seeded, other_user):
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other User", base_currency="EUR", is_active=True
    )
    _deposit(other_portfolio, day="2026-01-01", amount="5000")
    response = api_client.get(
        "/api/v1/cash/balances", {"portfolio_id": other_portfolio.id}
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_balances_unsupported_currency_400(api_client, seeded):
    response = api_client.get("/api/v1/cash/balances", {"currency": "XXX"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_balances_invalid_as_of_date_400(api_client, seeded):
    response = api_client.get(
        "/api/v1/cash/balances", {"as_of_date": "not-a-date"}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_ledger_paginated_sorted_desc(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _deposit(portfolio, day="2026-01-01", amount="100", note="first")
    _deposit(portfolio, day="2026-06-01", amount="200", note="second")

    response = api_client.get(
        "/api/v1/cash/ledger",
        {"portfolio_id": portfolio.id, "page_size": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert len(data["items"]) == 2
    assert data["items"][0]["date"] == "2026-06-01"
    assert data["items"][1]["date"] == "2026-01-01"
    assert data["items"][0]["entry_type"] == "CASH_DEPOSIT"
    assert data["items"][0]["portfolio_id"] == portfolio.id


@pytest.mark.django_db
def test_ledger_filters_currency_and_entry_type(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _deposit(portfolio, day="2026-01-01", amount="100")
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 1, 2),
        currency="EUR",
        entry_type=CashEntryType.CASH_WITHDRAWAL,
        amount=Decimal("-50"),
    )

    response = api_client.get(
        "/api/v1/cash/ledger",
        {"portfolio_id": portfolio.id, "entry_type": "CASH_WITHDRAWAL"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["amount"] == -50.0


@pytest.mark.django_db
def test_ledger_date_range_filter_and_invalid_range(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _deposit(portfolio, day="2026-01-01", amount="100")
    _deposit(portfolio, day="2026-06-01", amount="200")

    ok = api_client.get(
        "/api/v1/cash/ledger",
        {
            "portfolio_id": portfolio.id,
            "date_from": "2026-01-01",
            "date_to": "2026-02-01",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["total"] == 1

    bad = api_client.get(
        "/api/v1/cash/ledger",
        {
            "portfolio_id": portfolio.id,
            "date_from": "2026-06-01",
            "date_to": "2026-01-01",
        },
    )
    assert bad.status_code == 400


@pytest.mark.django_db
def test_ledger_user_scoping_hides_other_user_entries(
    api_client, seeded, test_user, other_user
):
    mine = ensure_default_portfolio(test_user)
    theirs = Portfolio.objects.create(
        user=other_user, name="Theirs", base_currency="EUR", is_active=True
    )
    _deposit(mine, day="2026-01-01", amount="100")
    _deposit(theirs, day="2026-01-01", amount="9000")

    response = api_client.get("/api/v1/cash/ledger")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["amount"] == 100.0


@pytest.mark.django_db
def test_portfolio_list_includes_cash_aware_enabled(api_client, seeded, test_user):
    from portfolios.seed import ensure_default_portfolio

    default = ensure_default_portfolio(test_user)
    assert default.cash_aware_enabled is True
    response = api_client.get("/api/v1/portfolios")
    assert response.status_code == 200
    default_row = next(p for p in response.json() if p["id"] == default.id)
    assert default_row["cash_aware_enabled"] is True


@pytest.mark.django_db
def test_portfolio_put_updates_cash_aware_enabled(api_client, seeded):
    created = api_client.post(
        "/api/v1/portfolios", {"name": "Cash Toggle"}, format="json"
    ).json()
    response = api_client.put(
        f"/api/v1/portfolios/{created['id']}",
        {"cash_aware_enabled": True},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["cash_aware_enabled"] is True


@pytest.mark.django_db
def test_unauthenticated_deposit_returns_401_or_403(anon_client, seeded):
    response = anon_client.post(
        "/api/v1/cash/deposits",
        {
            "portfolio_id": 1,
            "date": "2026-06-04",
            "currency": "EUR",
            "amount": "100",
        },
        format="json",
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_post_deposit_creates_positive_ledger_row(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    response = _post_deposit(api_client, portfolio.id)
    assert response.status_code == 201
    data = response.json()
    assert set(data.keys()) == LEDGER_ITEM_KEYS
    assert data["entry_type"] == "CASH_DEPOSIT"
    assert data["amount"] == 1000.0
    assert data["portfolio_id"] == portfolio.id
    row = CashLedgerEntry.objects.get(pk=data["id"])
    assert row.amount == Decimal("1000")


@pytest.mark.django_db
def test_post_withdrawal_creates_negative_ledger_row(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _post_deposit(api_client, portfolio.id, amount="1000", date="2026-06-01")
    response = _post_withdrawal(
        api_client, portfolio.id, amount="300", date="2026-06-04"
    )
    assert response.status_code == 201
    data = response.json()
    assert data["entry_type"] == "CASH_WITHDRAWAL"
    assert data["amount"] == -300.0
    row = CashLedgerEntry.objects.get(pk=data["id"])
    assert row.amount == Decimal("-300")


@pytest.mark.django_db
def test_deposit_and_withdrawal_reflect_in_balances(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _post_deposit(api_client, portfolio.id, amount="1000", date="2026-06-01")
    _post_withdrawal(api_client, portfolio.id, amount="250", date="2026-06-04")

    response = api_client.get(
        "/api/v1/cash/balances",
        {"portfolio_id": portfolio.id, "as_of_date": "2026-06-04"},
    )
    assert response.status_code == 200
    assert response.json()["balances"] == [{"currency": "EUR", "balance": 750.0}]


@pytest.mark.django_db
def test_withdrawal_insufficient_cash_returns_400(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _post_deposit(api_client, portfolio.id, amount="100", date="2026-06-01")
    response = _post_withdrawal(
        api_client, portfolio.id, amount="500", date="2026-06-04"
    )
    assert response.status_code == 400
    data = response.json()
    assert "Insufficient cash balance for withdrawal" in data["detail"]
    assert data["required"] == 500.0
    assert data["available"] == 100.0
    assert data["shortfall"] == 400.0
    assert data["currency"] == "EUR"


@pytest.mark.django_db
def test_withdrawal_sufficiency_same_currency_no_fx(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _post_deposit(api_client, portfolio.id, amount="100", date="2026-06-01", currency="EUR")
    _post_deposit(api_client, portfolio.id, amount="5000", date="2026-06-01", currency="INR")
    response = _post_withdrawal(
        api_client, portfolio.id, amount="50", date="2026-06-04", currency="EUR"
    )
    assert response.status_code == 201
    balances = api_client.get(
        "/api/v1/cash/balances", {"portfolio_id": portfolio.id}
    ).json()["balances"]
    by_ccy = {b["currency"]: b["balance"] for b in balances}
    assert by_ccy["EUR"] == 50.0
    assert by_ccy["INR"] == 5000.0


@pytest.mark.django_db
def test_deposit_other_user_portfolio_404(api_client, seeded, other_user):
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="EUR", is_active=True
    )
    response = _post_deposit(api_client, other_portfolio.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_deposit_inactive_portfolio_404(api_client, seeded, test_user):
    inactive = Portfolio.objects.create(
        user=test_user, name="Inactive", base_currency="EUR", is_active=False
    )
    response = _post_deposit(api_client, inactive.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_deposit_unknown_portfolio_404(api_client, seeded):
    assert _post_deposit(api_client, 999999).status_code == 404


@pytest.mark.django_db
def test_deposit_unsupported_currency_400(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    response = _post_deposit(api_client, portfolio.id, currency="XXX")
    assert response.status_code == 400


@pytest.mark.django_db
def test_deposit_zero_amount_400(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    response = _post_deposit(api_client, portfolio.id, amount="0")
    assert response.status_code == 400


@pytest.mark.django_db
def test_deposit_negative_request_amount_400(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    response = _post_deposit(api_client, portfolio.id, amount="-100")
    assert response.status_code == 400


@pytest.mark.django_db
def test_deposit_allowed_when_cash_aware_disabled(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    portfolio.cash_aware_enabled = False
    portfolio.save(update_fields=["cash_aware_enabled", "updated_at"])
    assert portfolio.cash_aware_enabled is False
    response = _post_deposit(api_client, portfolio.id)
    assert response.status_code == 201


@pytest.mark.django_db
def test_deposit_does_not_create_or_modify_transactions(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    before_ids = set(Transaction.objects.values_list("id", flat=True))
    before_count = Transaction.objects.count()
    response = _post_deposit(api_client, portfolio.id)
    assert response.status_code == 201
    assert Transaction.objects.count() == before_count
    assert set(Transaction.objects.values_list("id", flat=True)) == before_ids


@pytest.mark.django_db
def test_withdrawal_as_of_date_uses_ledger_on_or_before_date(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    _post_deposit(api_client, portfolio.id, amount="100", date="2026-06-01")
    _post_deposit(api_client, portfolio.id, amount="500", date="2026-06-10")
    response = _post_withdrawal(
        api_client, portfolio.id, amount="100", date="2026-06-05"
    )
    assert response.status_code == 201


def _put_ledger(api_client, entry_id, **overrides):
    payload = {
        "date": "2026-06-04",
        "currency": "EUR",
        "amount": "1000.00",
        "source_of_funds": "",
        "note": "",
    }
    payload.update(overrides)
    return api_client.put(f"/api/v1/cash/ledger/{entry_id}", payload, format="json")


@pytest.mark.django_db
def test_put_manual_deposit_updates_entry(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    created = _post_deposit(
        api_client, portfolio.id, amount="500", date="2026-06-01", note="old"
    ).json()
    response = _put_ledger(
        api_client,
        created["id"],
        date="2026-06-02",
        amount="750",
        note="updated",
        source_of_funds="Bank",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["entry_type"] == "CASH_DEPOSIT"
    assert data["amount"] == 750.0
    assert data["date"] == "2026-06-02"
    assert data["note"] == "updated"
    assert data["source_of_funds"] == "Bank"


@pytest.mark.django_db
def test_put_manual_withdrawal_updates_entry(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _post_deposit(api_client, portfolio.id, amount="1000", date="2026-06-01")
    created = _post_withdrawal(
        api_client, portfolio.id, amount="200", date="2026-06-04"
    ).json()
    response = _put_ledger(
        api_client, created["id"], amount="300", date="2026-06-05", note="less"
    )
    assert response.status_code == 200
    assert response.json()["amount"] == -300.0
    assert response.json()["note"] == "less"


@pytest.mark.django_db
def test_put_linked_settlement_entry_returns_409(api_client, seeded, test_user):
    from transactions.models import Transaction

    portfolio = ensure_default_portfolio(test_user)
    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="TST",
        date=date(2026, 6, 1),
        type="BUY",
        quantity=1,
        price_per_share=100,
        currency="EUR",
        fees=0,
    )
    entry = CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-100"),
        linked_transaction=txn,
    )
    response = _put_ledger(api_client, entry.id, amount="50")
    assert response.status_code == 409
    assert "cannot be edited directly" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_delete_manual_deposit_when_safe(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    created = _post_deposit(api_client, portfolio.id, amount="500", date="2026-06-01").json()
    response = api_client.delete(f"/api/v1/cash/ledger/{created['id']}")
    assert response.status_code == 204
    assert not CashLedgerEntry.objects.filter(pk=created["id"]).exists()


@pytest.mark.django_db
def test_delete_deposit_blocked_when_later_balance_negative(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    deposit = _post_deposit(
        api_client, portfolio.id, amount="1000", date="2026-06-01"
    ).json()
    _post_withdrawal(api_client, portfolio.id, amount="800", date="2026-06-10")
    response = api_client.delete(f"/api/v1/cash/ledger/{deposit['id']}")
    assert response.status_code == 409
    data = response.json()
    assert "future cash balance negative" in data["detail"].lower()
    assert data["currency"] == "EUR"
    assert data["earliest_negative_date"]
    assert data["lowest_balance"] < 0


@pytest.mark.django_db
def test_delete_deposit_blocked_by_buy_settlement_returns_affected_entries(
    api_client, seeded, test_user
):
    from transactions.models import Transaction

    portfolio = ensure_default_portfolio(test_user)
    deposit = _post_deposit(
        api_client, portfolio.id, amount="1000", date="2026-06-01"
    ).json()
    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="AAPL",
        date=date(2026, 6, 5),
        type="BUY",
        quantity=1,
        price_per_share=900,
        currency="EUR",
        fees=0,
    )
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 5),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-900"),
        linked_transaction=txn,
    )
    response = api_client.delete(f"/api/v1/cash/ledger/{deposit['id']}")
    assert response.status_code == 409
    data = response.json()
    assert data["affected_entries"]
    match = [e for e in data["affected_entries"] if e["entry_type"] == "BUY_SETTLEMENT"]
    assert len(match) == 1
    assert match[0]["linked_transaction_id"] == txn.id
    assert match[0]["asset_symbol"] == "AAPL"


@pytest.mark.django_db
def test_put_deposit_down_blocked_when_buy_settlement_would_go_negative(
    api_client, seeded, test_user
):
    from transactions.models import Transaction

    portfolio = ensure_default_portfolio(test_user)
    created = _post_deposit(
        api_client, portfolio.id, amount="1000", date="2026-06-01"
    ).json()
    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="MSFT",
        date=date(2026, 6, 4),
        type="BUY",
        quantity=1,
        price_per_share=800,
        currency="EUR",
        fees=0,
    )
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 4),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-800"),
        linked_transaction=txn,
    )
    response = _put_ledger(api_client, created["id"], amount="100", date="2026-06-01")
    assert response.status_code == 409
    assert response.json()["affected_entries"]


@pytest.mark.django_db
def test_put_deposit_currency_change_usd_to_eur_when_safe(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    created = _post_deposit(
        api_client, portfolio.id, amount="500", date="2026-06-01", currency="USD"
    ).json()
    response = _put_ledger(
        api_client,
        created["id"],
        currency="EUR",
        amount="500",
        date="2026-06-01",
    )
    assert response.status_code == 200
    assert response.json()["currency"] == "EUR"


@pytest.mark.django_db
def test_put_deposit_currency_change_blocked_when_old_currency_negative(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    created = _post_deposit(
        api_client, portfolio.id, amount="500", date="2026-06-01", currency="USD"
    ).json()
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 10),
        currency="USD",
        entry_type=CashEntryType.CASH_WITHDRAWAL,
        amount=Decimal("-400"),
    )
    response = _put_ledger(
        api_client,
        created["id"],
        currency="EUR",
        amount="500",
        date="2026-06-01",
    )
    assert response.status_code == 409
    assert response.json()["currency"] == "USD"


@pytest.mark.django_db
def test_delete_system_entry_returns_409(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-50"),
    )
    response = api_client.delete(f"/api/v1/cash/ledger/{entry.id}")
    assert response.status_code == 409


@pytest.mark.django_db
def test_put_ledger_other_user_404(api_client, seeded, test_user, other_user):
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="EUR", is_active=True
    )
    entry = CashLedgerEntry.objects.create(
        portfolio=other_portfolio,
        date=date(2026, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("100"),
    )
    response = _put_ledger(api_client, entry.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_put_withdrawal_insufficient_on_edit(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _post_deposit(api_client, portfolio.id, amount="100", date="2026-06-01")
    created = _post_withdrawal(
        api_client, portfolio.id, amount="50", date="2026-06-04"
    ).json()
    response = _put_ledger(api_client, created["id"], amount="200")
    assert response.status_code == 400
    data = response.json()
    assert "Insufficient" in data["detail"]
    assert data["required"] == 200.0
    # Edit excludes the row being changed; only the deposit remains on that date.
    assert data["available"] == 100.0


@pytest.mark.django_db
def test_put_ledger_invalid_currency_400(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    created = _post_deposit(api_client, portfolio.id).json()
    response = _put_ledger(api_client, created["id"], currency="XXX")
    assert response.status_code == 400


@pytest.mark.django_db
def test_put_ledger_does_not_modify_transactions(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    created = _post_deposit(api_client, portfolio.id).json()
    before = set(Transaction.objects.values_list("id", flat=True))
    _put_ledger(api_client, created["id"], amount="900", note="x")
    assert set(Transaction.objects.values_list("id", flat=True)) == before
