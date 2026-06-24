from datetime import date
from decimal import Decimal

import pytest

from debt.models import BankAccount
from debt.services import create_bank_account, create_fixed_deposit, update_bank_account
from fx.models import FXRate
from market_data.models import HistoricalPrice
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_legacy_fixed_deposit_with_opening, create_test_bank_account, fund_bank_account
from transactions.models import Transaction


def _bank(user, portfolio=None, account_number="111"):
    return create_test_bank_account(user, portfolio=portfolio, account_number=account_number)



def _create_fd(user, portfolio_id, bank_id, principal="100000", status="ACTIVE", **kw):
    bank = BankAccount.objects.get(pk=bank_id)
    fund_bank_account(user, bank, Decimal(principal) + Decimal("50000"))
    return create_fixed_deposit(
        user,
        portfolio_id=portfolio_id,
        bank_account_id=bank_id,
        institution_name="HDFC",
        deposit_account_number=kw.get("deposit_account_number", "FD-1"),
        principal_amount=Decimal(principal),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
        status=status,
    )


def _seed_stock(api_client, portfolio, symbol="AAPL", qty=10, price=100):
    Transaction.objects.create(
        portfolio=portfolio,
        date=date(2024, 6, 1),
        type="BUY",
        asset_symbol=symbol,
        quantity=Decimal(qty),
        price_per_share=Decimal(price),
        currency="USD",
        fees=Decimal("0"),
    )
    HistoricalPrice.objects.update_or_create(
        asset_symbol=symbol,
        date=date(2024, 6, 1),
        defaults={"close_price": Decimal(price), "currency": "USD", "asset_type": "STOCK"},
    )
    HistoricalPrice.objects.update_or_create(
        asset_symbol=symbol,
        date=date.today(),
        defaults={"close_price": Decimal(price), "currency": "USD", "asset_type": "STOCK"},
    )
    FXRate.objects.update_or_create(
        from_currency="USD",
        to_currency="EUR",
        date=date.today(),
        defaults={"rate": Decimal("0.9")},
    )


@pytest.mark.django_db
def test_summary_includes_fd_principal(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id, principal="100000")
    FXRate.objects.update_or_create(
        from_currency="INR",
        to_currency="EUR",
        date=date.today(),
        defaults={"rate": Decimal("0.011")},
    )

    baseline = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert baseline["current_value"] >= 1100.0
    assert baseline["total_invested"] >= 1100.0
    assert baseline["unrealized_pl"] == pytest.approx(baseline["current_value"] - baseline["total_invested"])


@pytest.mark.django_db
def test_fd_unrealized_pl_zero_mvp(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id)
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    # Only FD in portfolio — unrealized should be 0 (principal-only)
    assert data["unrealized_pl"] == 0.0


@pytest.mark.django_db
def test_closed_fd_excluded_from_summary(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id, status="CLOSED")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 0.0


@pytest.mark.django_db
def test_inactive_fd_excluded_from_summary(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)
    fd.is_active = False
    fd.save()
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 0.0


@pytest.mark.django_db
def test_all_scope_aggregates_fds(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Second", base_currency="INR", is_active=True
    )
    bank1 = _bank(test_user, portfolio=p1, account_number="111-A")
    bank2 = _bank(test_user, portfolio=p2, account_number="111-B")
    _create_fd(test_user, p1.id, bank1.id, principal="50000", deposit_account_number="A")
    _create_fd(test_user, p2.id, bank2.id, principal="75000", deposit_account_number="B")

    data = api_client.get(
        "/api/v1/portfolio/summary?portfolio_scope=all&include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 125000.0


@pytest.mark.django_db
def test_single_portfolio_scope_fd_only(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Second", base_currency="INR", is_active=True
    )
    bank1 = _bank(test_user, portfolio=p1, account_number="111-A")
    bank2 = _bank(test_user, portfolio=p2, account_number="111-B")
    _create_fd(test_user, p1.id, bank1.id, principal="50000", deposit_account_number="A")
    _create_fd(test_user, p2.id, bank2.id, principal="75000", deposit_account_number="B")

    data = api_client.get(
        f"/api/v1/portfolio/summary?portfolio_id={p1.id}&include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 50000.0


@pytest.mark.django_db
def test_holdings_includes_fd_row(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id)
    holdings = api_client.get(
        "/api/v1/portfolio/holdings?display_currency=INR"
    ).json()["holdings"]
    fd_rows = [h for h in holdings if h.get("asset_type") == "FIXED_DEPOSIT"]
    assert len(fd_rows) == 1
    assert fd_rows[0]["institution_name"] == "HDFC"
    assert fd_rows[0]["principal_amount"] == 100000.0
    assert fd_rows[0]["value_status"] == "principal_only"


@pytest.mark.django_db
def test_summary_allocation_buckets_include_debt(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id)
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    buckets = {b["label"]: b["value"] for b in data["allocation_buckets"]["buckets"]}
    assert buckets["Debt"] == 100000.0


@pytest.mark.django_db
def test_stock_summary_not_regressed(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    _seed_stock(api_client, portfolio)
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert data["current_value"] == pytest.approx(900.0, rel=0.01)


@pytest.mark.django_db
def test_matured_fd_included_in_summary(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id, status="MATURED")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 100000.0
    assert data["has_fixed_deposits"] is True


@pytest.mark.django_db
def test_soft_delete_fd_excludes_from_summary(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank.id)
    cancel_resp = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/cancel",
        {"cancellation_date": "2024-06-15"},
        format="json",
    )
    assert cancel_resp.status_code == 200
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 0.0
    assert data.get("has_fixed_deposits") is not True


@pytest.mark.django_db
def test_allocation_buckets_fd_not_double_counted(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id)
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    buckets = {b["label"]: b["value"] for b in data["allocation_buckets"]["buckets"]}
    assert buckets.get("Equity", 0) == 0
    assert buckets["Debt"] == 100000.0


@pytest.mark.django_db
def test_performance_value_includes_fd_principal(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id)
    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    perf = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=INR"
    ).json()
    assert summary["current_value"] == 100000.0
    assert summary["has_fixed_deposits"] is True
    if isinstance(perf, list) and perf:
        last_val = perf[-1].get("value")
        assert last_val == pytest.approx(summary["current_value"], rel=1e-6)


@pytest.mark.django_db
def test_bank_account_balance_not_in_summary(seeded, test_user, api_client):
    create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="999",
        currency="INR",
        current_balance=Decimal("50000"),
    )
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 0.0


@pytest.mark.django_db
def test_holdings_fd_row_safe_fields(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank.id)
    row = [
        h
        for h in api_client.get("/api/v1/portfolio/holdings?display_currency=INR").json()[
            "holdings"
        ]
        if h.get("asset_type") == "FIXED_DEPOSIT"
    ][0]
    assert row["asset_symbol"].startswith("FD ")
    assert "price_status" not in row
    assert "nav_status" not in row
    assert row["value_status"] == "principal_only"
    assert row["maturity_date"] == "2026-01-01"


def _enable_bank_inclusion(user, bank: BankAccount) -> BankAccount:
    return update_bank_account(user, bank.id, include_in_portfolio_value=True)


@pytest.mark.django_db
def test_default_bank_account_excluded_from_summary(api_client, seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "75000")
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 0.0


@pytest.mark.django_db
def test_included_bank_account_appears_in_all_scope_summary(api_client, seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "75000")
    _enable_bank_inclusion(test_user, bank)
    data = api_client.get(
        "/api/v1/portfolio/summary?portfolio_scope=all&include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 75000.0
    assert data["total_invested"] == 75000.0


@pytest.mark.django_db
def test_included_bank_account_allocation_cash_bucket(api_client, seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "42000")
    _enable_bank_inclusion(test_user, bank)
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    buckets = {b["label"]: b["value"] for b in data["allocation_buckets"]["buckets"]}
    assert buckets["Cash / Bank Cash"] == 42000.0


@pytest.mark.django_db
def test_unseeded_manual_balance_not_in_portfolio_value(api_client, seeded, test_user):
    bank = create_bank_account(
        test_user,
        name="Manual",
        institution_name="HDFC",
        account_number="manual-1",
        currency="INR",
        current_balance=Decimal("99000"),
    )
    _enable_bank_inclusion(test_user, bank)
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 0.0


@pytest.mark.django_db
def test_fd_create_with_included_bank_cash_keeps_total_stable(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "200000")
    _enable_bank_inclusion(test_user, bank)

    before = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()["current_value"]
    assert before == 200000.0

    create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-STABLE",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )

    after = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()["current_value"]
    assert after == pytest.approx(200000.0, rel=0.001)


@pytest.mark.django_db
def test_fd_settlement_with_included_bank_cash_keeps_principal_stable(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    fd = create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-SETTLE",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    _enable_bank_inclusion(test_user, bank)

    before = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()["current_value"]

    settle = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        {
            "settlement_type": "MATURITY",
            "settlement_date": "2026-01-01",
            "gross_interest": 5000,
            "tax_withheld": 500,
        },
        format="json",
    )
    assert settle.status_code == 201

    after = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()["current_value"]
    # Principal stable; net final interest (+4500) increases total.
    assert after == pytest.approx(before + 4500.0, rel=0.001)


@pytest.mark.django_db
def test_fd_interest_payment_increases_included_cash(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "150000")
    fd = create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-INT",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    _enable_bank_inclusion(test_user, bank)

    before = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()["current_value"]

    payment = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/interest-payments",
        {
            "payment_date": "2025-06-01",
            "gross_interest": 1000,
            "tax_withheld": 100,
        },
        format="json",
    )
    assert payment.status_code == 201

    after = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()["current_value"]
    assert after == pytest.approx(before + 900.0, rel=0.001)


@pytest.mark.django_db
def test_single_portfolio_scope_includes_exclusive_bank_account(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "60000")
    _enable_bank_inclusion(test_user, bank)
    create_fixed_deposit(
        test_user,
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-SINGLE",
        principal_amount=Decimal("10000"),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )

    data = api_client.get(
        f"/api/v1/portfolio/summary?portfolio_id={portfolio.id}&include_timeseries=false&display_currency=INR"
    ).json()
    # Bank cash (50k after FD debit) + FD principal (10k)
    assert data["current_value"] == pytest.approx(60000.0, rel=0.001)


@pytest.mark.django_db
def test_single_portfolio_scope_excludes_multi_portfolio_bank_account(
    api_client, seeded, test_user
):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Second", base_currency="INR", is_active=True
    )
    bank = create_bank_account(
        test_user,
        name="Savings",
        institution_name="HDFC",
        account_number="scope-shared",
        currency="INR",
    )
    fund_bank_account(test_user, bank, "80000")
    create_legacy_fixed_deposit_with_opening(
        test_user,
        portfolio=p1,
        bank=bank,
        deposit_account_number="A",
        principal_amount=Decimal("10000"),
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    create_legacy_fixed_deposit_with_opening(
        test_user,
        portfolio=p2,
        bank=bank,
        deposit_account_number="B",
        principal_amount=Decimal("20000"),
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    _enable_bank_inclusion(test_user, bank)

    all_data = api_client.get(
        "/api/v1/portfolio/summary?portfolio_scope=all&include_timeseries=false&display_currency=INR"
    ).json()
    p1_data = api_client.get(
        f"/api/v1/portfolio/summary?portfolio_id={p1.id}&include_timeseries=false&display_currency=INR"
    ).json()

    assert all_data["current_value"] == pytest.approx(80000.0, rel=0.001)
    assert p1_data["current_value"] == 10000.0


@pytest.mark.django_db
def test_bank_cash_not_double_counted_in_all_scope(api_client, seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "33000")
    _enable_bank_inclusion(test_user, bank)
    data = api_client.get(
        "/api/v1/portfolio/summary?portfolio_scope=all&include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 33000.0


@pytest.mark.django_db
def test_other_user_bank_cash_excluded(api_client, seeded, test_user, django_user_model):
    other = django_user_model.objects.create_user(
        username="other-bank", email="other@example.com", password="pass"
    )
    bank = create_bank_account(
        other,
        name="Other savings",
        institution_name="SBI",
        account_number="other-1",
        currency="INR",
    )
    fund_bank_account(other, bank, "50000")
    update_bank_account(other, bank.id, include_in_portfolio_value=True)

    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert data["current_value"] == 0.0


@pytest.mark.django_db
def test_bank_cash_fx_conversion_in_summary(api_client, seeded, test_user):
    bank = create_bank_account(
        test_user,
        name="USD savings",
        institution_name="Chase",
        account_number="usd-1",
        currency="USD",
    )
    fund_bank_account(test_user, bank, "1000")
    _enable_bank_inclusion(test_user, bank)
    FXRate.objects.update_or_create(
        from_currency="USD",
        to_currency="EUR",
        date=date.today(),
        defaults={"rate": Decimal("0.9")},
    )
    data = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=EUR"
    ).json()
    assert data["current_value"] == pytest.approx(900.0, rel=0.01)


@pytest.mark.django_db
def test_holdings_includes_bank_cash_row(api_client, seeded, test_user):
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "25000")
    _enable_bank_inclusion(test_user, bank)
    rows = api_client.get("/api/v1/portfolio/holdings?display_currency=INR").json()[
        "holdings"
    ]
    bank_rows = [h for h in rows if h.get("asset_type") == "BANK_CASH"]
    assert len(bank_rows) == 1
    assert bank_rows[0]["asset_symbol"] == "Savings"
    assert bank_rows[0]["current_value"] == 25000.0
    assert "quantity" not in bank_rows[0]
    assert bank_rows[0]["unrealized_pl"] == 0.0
