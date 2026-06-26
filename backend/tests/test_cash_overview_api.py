from datetime import date
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry
from debt.services import create_bank_account, create_fixed_deposit
from fx.models import FXRate
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_legacy_fixed_deposit, fund_bank_account


def _deposit(portfolio, *, amount: str, currency: str = "EUR"):
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency=currency,
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
    )


def _create_bank(user, portfolio_id=None, **overrides):
    payload = dict(
        name="Savings",
        institution_name="HDFC",
        account_number="ACC-OVR",
        currency="INR",
    )
    if portfolio_id is not None:
        payload["portfolio_id"] = portfolio_id
    payload.update(overrides)
    return create_bank_account(user, **payload)


def _fd_payload(portfolio_id, bank_id, **overrides):
    payload = dict(
        portfolio_id=portfolio_id,
        bank_account_id=bank_id,
        institution_name="HDFC",
        deposit_account_number="FD-OVR",
        principal_amount=Decimal("50000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 6, 1),
        maturity_date=date(2025, 6, 1),
    )
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_overview_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/cash/overview")
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_overview_all_scope_broker_and_assigned_bank(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _deposit(portfolio, amount="1500")
    bank = _create_bank(test_user, portfolio_id=portfolio.id)
    fund_bank_account(test_user, bank, "25000")

    response = api_client.get("/api/v1/cash/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_scope"] == "all"
    ledger_types = {row["ledger_type"] for row in body["rows"]}
    assert "BROKER_CASH" in ledger_types
    assert "BANK_CASH" in ledger_types

    broker = next(r for r in body["rows"] if r["ledger_type"] == "BROKER_CASH")
    assert broker["balance"] == 1500.0
    assert broker["available_for"] == "securities / broker transactions"

    bank_row = next(r for r in body["rows"] if r["ledger_type"] == "BANK_CASH")
    assert bank_row["balance"] == 25000.0
    assert bank_row["portfolio_assignment_status"] == "ASSIGNED"
    assert bank_row["available_for"] == "fixed deposits / bank products"


@pytest.mark.django_db
def test_overview_single_portfolio_scope(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Other PF", base_currency="EUR", is_active=True
    )
    _deposit(p1, amount="1000")
    _deposit(p2, amount="2000", currency="EUR")
    bank_p1 = _create_bank(test_user, portfolio_id=p1.id, account_number="P1")
    bank_p2 = _create_bank(
        test_user, portfolio_id=p2.id, name="Other bank", account_number="P2"
    )
    fund_bank_account(test_user, bank_p1, "10000")
    fund_bank_account(test_user, bank_p2, "20000")

    response = api_client.get(
        "/api/v1/cash/overview", {"portfolio_id": p1.id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] == p1.id
    broker_balances = [
        r["balance"]
        for r in body["rows"]
        if r["ledger_type"] == "BROKER_CASH"
    ]
    assert broker_balances == [1000.0]
    bank_ids = [
        r["bank_account_id"]
        for r in body["rows"]
        if r["ledger_type"] == "BANK_CASH"
    ]
    assert bank_ids == [bank_p1.id]


@pytest.mark.django_db
def test_overview_excludes_unassigned_bank_by_default(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _deposit(portfolio, amount="500")
    bank = _create_bank(test_user)
    fund_bank_account(test_user, bank, "9000")

    response = api_client.get("/api/v1/cash/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["excluded_unassigned_bank_account_count"] == 1
    assert any("portfolio link" in w.lower() for w in body["warnings"])
    assert all(r["ledger_type"] != "BANK_CASH" for r in body["rows"])


@pytest.mark.django_db
def test_overview_include_unassigned_flag(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _create_bank(test_user)
    fund_bank_account(test_user, bank, "9000")

    response = api_client.get(
        "/api/v1/cash/overview", {"include_unassigned": "true"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["excluded_unassigned_bank_account_count"] == 0
    bank_rows = [r for r in body["rows"] if r["ledger_type"] == "BANK_CASH"]
    assert len(bank_rows) == 1
    assert bank_rows[0]["portfolio_assignment_status"] == "UNASSIGNED"


@pytest.mark.django_db
def test_overview_excludes_ambiguous_bank(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Other", base_currency="INR", is_active=True
    )
    bank = _create_bank(test_user)
    create_legacy_fixed_deposit(test_user, portfolio=p1, bank=bank, deposit_account_number="FD-1")
    create_legacy_fixed_deposit(
        test_user,
        portfolio=p2,
        bank=bank,
        deposit_account_number="FD-2",
        investment_date=date(2024, 7, 1),
        maturity_date=date(2025, 7, 1),
    )

    response = api_client.get("/api/v1/cash/overview")
    body = response.json()
    assert body["excluded_ambiguous_bank_account_count"] == 1
    assert all(r["ledger_type"] != "BANK_CASH" for r in body["rows"])


@pytest.mark.django_db
def test_overview_display_currency_conversion(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _deposit(portfolio, amount="100", currency="EUR")
    FXRate.objects.update_or_create(
        from_currency="EUR",
        to_currency="USD",
        date=date(2026, 6, 1),
        defaults={"rate": Decimal("1.10")},
    )

    response = api_client.get(
        "/api/v1/cash/overview",
        {"display_currency": "USD", "as_of_date": "2026-06-01"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_currency"] == "USD"
    broker = next(r for r in body["rows"] if r["ledger_type"] == "BROKER_CASH")
    assert broker["balance_display"] == pytest.approx(110.0)
    assert body["totals"]["fx_status"] == "ok"
    assert body["totals"]["total_cash_display"] == pytest.approx(110.0)


@pytest.mark.django_db
def test_overview_missing_fx_warning(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _deposit(portfolio, amount="100", currency="EUR")

    response = api_client.get(
        "/api/v1/cash/overview",
        {"display_currency": "USD", "as_of_date": "2026-06-01"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["fx_status"] == "fx_unavailable"
    assert body["totals"]["total_cash_display"] is None
    assert any("FX unavailable" in w for w in body["warnings"])


@pytest.mark.django_db
def test_overview_totals_not_swapped_broker_zero_bank_positive(api_client, seeded, test_user):
    """Regression: broker and bank native totals must not be swapped (CASH-UNIFY-3A)."""
    portfolio = Portfolio.objects.create(
        user=test_user,
        name="IndianInvestments",
        base_currency="INR",
        is_active=True,
    )
    bank = _create_bank(test_user, portfolio_id=portfolio.id, account_number="IN-1")
    fund_bank_account(test_user, bank, "1109389")

    response = api_client.get(
        "/api/v1/cash/overview", {"portfolio_id": portfolio.id}
    )
    assert response.status_code == 200
    body = response.json()

    broker_rows = [r for r in body["rows"] if r["ledger_type"] == "BROKER_CASH"]
    bank_rows = [r for r in body["rows"] if r["ledger_type"] == "BANK_CASH"]
    assert broker_rows == []
    assert len(bank_rows) == 1
    assert bank_rows[0]["balance"] == pytest.approx(1109389.0)
    assert bank_rows[0]["source"] == "cash_movements"
    assert all(r["ledger_type"] != "BROKER_CASH" or r["balance"] == 0 for r in body["rows"])

    inr_totals = next(t for t in body["totals"]["by_currency"] if t["currency"] == "INR")
    assert inr_totals["broker_cash"] == 0.0
    assert inr_totals["bank_cash"] == pytest.approx(1109389.0)
    assert inr_totals["total_cash"] == pytest.approx(1109389.0)


@pytest.mark.django_db
def test_overview_user_scoped(api_client, seeded, test_user, other_user):
    portfolio = ensure_default_portfolio(test_user)
    _deposit(portfolio, amount="100")
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other user PF", base_currency="EUR", is_active=True
    )
    CashLedgerEntry.objects.create(
        portfolio=other_portfolio,
        date=date(2026, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("9999"),
    )

    response = api_client.get("/api/v1/cash/overview")
    body = response.json()
    assert all(r.get("balance") != 9999.0 for r in body["rows"])


@pytest.mark.django_db
def test_overview_get_does_not_mutate_ledger(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _create_bank(test_user, portfolio_id=portfolio.id)
    fund_bank_account(test_user, bank, "1000")
    before_entries = CashLedgerEntry.objects.count()
    before_bank = bank.current_balance

    api_client.get("/api/v1/cash/overview")
    assert CashLedgerEntry.objects.count() == before_entries
    bank.refresh_from_db()
    assert bank.current_balance == before_bank


@pytest.mark.django_db
def test_overview_relink_moves_bank_between_portfolios(api_client, seeded, test_user):
    from debt.models import CashMovement
    from portfolios.models import Portfolio
    from portfolios.seed import ensure_default_portfolio

    default_pf = ensure_default_portfolio(test_user)
    indian_pf = Portfolio.objects.create(
        user=test_user,
        name="IndianInvestments",
        base_currency="INR",
        is_active=True,
    )
    bank = _create_bank(test_user, portfolio_id=default_pf.id, account_number="HDFC-NRE")
    fund_bank_account(test_user, bank, "1359389")
    movement_count_before = CashMovement.objects.filter(bank_account=bank).count()

    default_view = api_client.get(
        "/api/v1/cash/overview", {"portfolio_id": default_pf.id}
    ).json()
    assert len([r for r in default_view["rows"] if r.get("bank_account_id") == bank.id]) == 1
    indian_view = api_client.get(
        "/api/v1/cash/overview", {"portfolio_id": indian_pf.id}
    ).json()
    assert all(r.get("bank_account_id") != bank.id for r in indian_view["rows"])

    api_client.put(
        f"/api/v1/bank-accounts/{bank.id}",
        {"portfolio_id": indian_pf.id},
        format="json",
    )

    default_after = api_client.get(
        "/api/v1/cash/overview", {"portfolio_id": default_pf.id}
    ).json()
    assert all(r.get("bank_account_id") != bank.id for r in default_after["rows"])
    indian_after = api_client.get(
        "/api/v1/cash/overview", {"portfolio_id": indian_pf.id}
    ).json()
    bank_rows = [r for r in indian_after["rows"] if r.get("bank_account_id") == bank.id]
    assert len(bank_rows) == 1
    assert bank_rows[0]["balance"] == pytest.approx(1359389.0)

    assert CashMovement.objects.filter(bank_account=bank).count() == movement_count_before
    bank.refresh_from_db()
    assert bank.current_balance == pytest.approx(Decimal("1359389"))


@pytest.mark.django_db
def test_overview_all_scope_no_double_count_after_relink(api_client, seeded, test_user):
    from portfolios.models import Portfolio
    from portfolios.seed import ensure_default_portfolio

    default_pf = ensure_default_portfolio(test_user)
    indian_pf = Portfolio.objects.create(
        user=test_user,
        name="IndianInvestments",
        base_currency="INR",
        is_active=True,
    )
    bank = _create_bank(test_user, portfolio_id=default_pf.id, account_number="HDFC-NRE")
    fund_bank_account(test_user, bank, "100000")

    api_client.put(
        f"/api/v1/bank-accounts/{bank.id}",
        {"portfolio_id": indian_pf.id},
        format="json",
    )

    body = api_client.get("/api/v1/cash/overview").json()
    bank_rows = [r for r in body["rows"] if r.get("bank_account_id") == bank.id]
    assert len(bank_rows) == 1
    assert bank_rows[0]["portfolio_id"] == indian_pf.id


@pytest.mark.django_db
def test_overview_delinked_bank_hidden_until_include_unassigned(api_client, seeded, test_user):
    from portfolios.seed import ensure_default_portfolio

    portfolio = ensure_default_portfolio(test_user)
    bank = _create_bank(test_user, portfolio_id=portfolio.id)
    fund_bank_account(test_user, bank, "50000")

    api_client.put(
        f"/api/v1/bank-accounts/{bank.id}",
        {"portfolio_id": None},
        format="json",
    )

    scoped = api_client.get(
        "/api/v1/cash/overview", {"portfolio_id": portfolio.id}
    ).json()
    assert all(r.get("bank_account_id") != bank.id for r in scoped["rows"])
    assert scoped["excluded_unassigned_bank_account_count"] >= 1

    with_flag = api_client.get(
        "/api/v1/cash/overview", {"include_unassigned": "true"}
    ).json()
    bank_rows = [r for r in with_flag["rows"] if r.get("bank_account_id") == bank.id]
    assert len(bank_rows) == 1
    assert bank_rows[0]["portfolio_assignment_status"] == "UNASSIGNED"
