from datetime import date
from decimal import Decimal

import pytest

from debt.models import (
    CashMovement,
    CashMovementType,
    FixedDeposit,
    FixedDepositRenewalGroup,
    FixedDepositSettlement,
    FixedDepositStatus,
)
from debt.services import create_bank_account, create_fixed_deposit
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _bank(user, portfolio=None, **overrides):
    return create_test_bank_account(user, portfolio=portfolio, **overrides)



def _fd_payload(portfolio_id, bank_account_id, **overrides):
    payload = dict(
        portfolio_id=portfolio_id,
        bank_account_id=bank_account_id,
        institution_name="HDFC",
        deposit_account_number="FD-001",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7.0"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    payload.update(overrides)
    return payload


def _create_fd(user, portfolio_id, bank, **overrides):
    fund_bank_account(user, bank, "200000")
    return create_fixed_deposit(user, **_fd_payload(portfolio_id, bank.id, **overrides))


def _renew_payload(**overrides):
    payload = dict(
        renewal_date=date(2026, 1, 1),
        new_deposit_account_number="FD-002",
        new_principal_amount=Decimal("100000"),
        new_interest_rate_percent=Decimal("7.5"),
        new_interest_payout_frequency="QUARTERLY",
        new_investment_date=date(2026, 1, 1),
        new_maturity_date=date(2028, 1, 1),
    )
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_renew_active_fd_creates_new_fd_with_renewal_of(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["old_fixed_deposit"]["id"] == fd.id
    assert body["old_fixed_deposit"]["status"] == "MATURED_SETTLED"
    assert body["new_fixed_deposit"]["status"] == "ACTIVE"
    assert body["direct_reinvest_amount"] == 100000.0
    assert body["cash_payout_amount"] == 0.0
    assert body["cash_movement_ids"] == []

    new_fd = FixedDeposit.objects.get(id=body["new_fixed_deposit"]["id"])
    assert new_fd.renewal_of_id == fd.id
    assert new_fd.principal_amount == Decimal("100000")
    assert not CashMovement.objects.filter(
        linked_fixed_deposit=new_fd,
        movement_type=CashMovementType.FD_OPENING,
    ).exists()


@pytest.mark.django_db
def test_renew_matured_fd_works(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank, status=FixedDepositStatus.MATURED)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(new_deposit_account_number="FD-MAT"),
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["old_fixed_deposit"]["status"] == "MATURED_SETTLED"


@pytest.mark.django_db
def test_renew_no_fd_opening_debit_for_direct_rollover(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    opening_count_before = CashMovement.objects.filter(
        movement_type=CashMovementType.FD_OPENING
    ).count()

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(),
        format="json",
    )
    assert response.status_code == 201
    new_fd_id = response.json()["new_fixed_deposit"]["id"]
    assert (
        CashMovement.objects.filter(
            linked_fixed_deposit_id=new_fd_id,
            movement_type=CashMovementType.FD_OPENING,
        ).count()
        == 0
    )
    assert (
        CashMovement.objects.filter(movement_type=CashMovementType.FD_OPENING).count()
        == opening_count_before
    )


@pytest.mark.django_db
def test_normal_fd_create_still_creates_fd_opening_debit(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fund_bank_account(test_user, bank, "200000")

    response = api_client.post(
        "/api/v1/fixed-deposits",
        _fd_payload(portfolio.id, bank.id, deposit_account_number="FD-NORMAL"),
        format="json",
    )
    assert response.status_code == 201
    fd_id = response.json()["id"]
    assert response.json()["has_opening_cash_movement"] is True
    assert CashMovement.objects.filter(
        linked_fixed_deposit_id=fd_id,
        movement_type=CashMovementType.FD_OPENING,
    ).exists()


@pytest.mark.django_db
def test_partial_cash_payout_creates_bank_credit(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    bank.refresh_from_db()
    balance_before = bank.current_balance

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(
            new_principal_amount=Decimal("90000"),
            cash_payout_amount=Decimal("10000"),
        ),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["cash_payout_amount"] == 10000.0
    assert len(body["cash_movement_ids"]) == 1

    payout_mv = CashMovement.objects.get(id=body["cash_movement_ids"][0])
    assert payout_mv.movement_type == CashMovementType.FD_MATURITY_PRINCIPAL
    bank.refresh_from_db()
    assert bank.current_balance == balance_before + Decimal("10000")


@pytest.mark.django_db
def test_net_interest_cash_payment_creates_bank_credit(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    bank.refresh_from_db()
    balance_before = bank.current_balance

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(gross_interest=Decimal("5000"), tax_withheld=Decimal("500")),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["net_interest"] == 4500.0
    assert len(body["cash_movement_ids"]) == 1

    interest_mv = CashMovement.objects.get(id=body["cash_movement_ids"][0])
    assert interest_mv.movement_type == CashMovementType.FD_MATURITY_INTEREST
    bank.refresh_from_db()
    assert bank.current_balance == balance_before + Decimal("4500")


@pytest.mark.django_db
def test_reject_tax_withheld_exceeds_gross(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(gross_interest=Decimal("1000"), tax_withheld=Decimal("1500")),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_closed_fd_renewal(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank, status=FixedDepositStatus.CLOSED)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_matured_settled_fd_renewal(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        {
            "settlement_type": "MATURITY",
            "settlement_date": "2026-01-01",
            "gross_interest": "0",
            "tax_withheld": "0",
        },
        format="json",
    )

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_already_renewed_fd(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(),
        format="json",
    )

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(new_deposit_account_number="FD-003"),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_reject_foreign_fd(api_client, seeded, test_user, other_user):
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="INR", is_active=True
    )
    other_bank = _bank(other_user, portfolio=other_portfolio, account_number="OTHER")
    other_fd = _create_fd(other_user, other_portfolio.id, other_bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{other_fd.id}/renew",
        _renew_payload(),
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_reject_invalid_maturity_date(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(
            new_investment_date=date(2026, 1, 1),
            new_maturity_date=date(2026, 1, 1),
        ),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_portfolio_summary_after_renewal_uses_new_principal_only(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank, principal_amount=Decimal("100000"))

    summary_before = api_client.get(
        f"/api/v1/portfolio/summary?portfolio_id={portfolio.id}&include_timeseries=false&display_currency=INR"
    ).json()
    assert summary_before["current_value"] >= 100000.0

    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(new_principal_amount=Decimal("120000")),
        format="json",
    )

    summary_after = api_client.get(
        f"/api/v1/portfolio/summary?portfolio_id={portfolio.id}&include_timeseries=false&display_currency=INR"
    ).json()
    fd_total = sum(
        float(h.get("current_value", 0))
        for h in api_client.get(
            f"/api/v1/portfolio/holdings?portfolio_id={portfolio.id}&display_currency=INR"
        ).json().get("holdings", [])
        if h.get("asset_type") == "FIXED_DEPOSIT"
    )
    assert fd_total == 120000.0
    assert summary_after["current_value"] == summary_before["current_value"] - 100000.0 + 120000.0


@pytest.mark.django_db
def test_bank_cash_not_in_portfolio_summary_after_renewal_with_payout(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    summary_before = api_client.get(
        f"/api/v1/portfolio/summary?portfolio_id={portfolio.id}&include_timeseries=false&display_currency=INR"
    ).json()

    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(
            new_principal_amount=Decimal("90000"),
            cash_payout_amount=Decimal("10000"),
            gross_interest=Decimal("5000"),
            tax_withheld=Decimal("500"),
        ),
        format="json",
    )

    summary_after = api_client.get(
        f"/api/v1/portfolio/summary?portfolio_id={portfolio.id}&include_timeseries=false&display_currency=INR"
    ).json()
    bank.refresh_from_db()
    assert bank.current_balance > 0
    assert summary_after["current_value"] == summary_before["current_value"] - 100000.0 + 90000.0


@pytest.mark.django_db
def test_renewal_creates_renewal_group_and_settlement(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert FixedDepositRenewalGroup.objects.filter(id=body["renewal_id"]).exists()
    assert FixedDepositSettlement.objects.filter(id=body["settlement_id"]).exists()


@pytest.mark.django_db
def test_atomic_failure_on_invalid_request(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    fd_count_before = FixedDeposit.objects.count()
    settlement_count_before = FixedDepositSettlement.objects.count()
    renewal_count_before = FixedDepositRenewalGroup.objects.count()

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(new_principal_amount=Decimal("0")),
        format="json",
    )
    assert response.status_code == 400
    fd.refresh_from_db()
    assert fd.status == FixedDepositStatus.ACTIVE
    assert FixedDeposit.objects.count() == fd_count_before
    assert FixedDepositSettlement.objects.count() == settlement_count_before
    assert FixedDepositRenewalGroup.objects.count() == renewal_count_before


@pytest.mark.django_db
def test_list_fd_includes_has_renewal_flag(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(),
        format="json",
    )

    items = api_client.get("/api/v1/fixed-deposits").json()
    old_row = next(item for item in items if item["id"] == fd.id)
    new_row = next(item for item in items if item["id"] != fd.id)
    assert old_row["has_renewal"] is True
    assert new_row["has_renewal"] is False
