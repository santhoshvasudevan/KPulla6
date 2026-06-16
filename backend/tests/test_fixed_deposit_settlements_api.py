from datetime import date
from decimal import Decimal

import pytest

from debt.models import (
    CashMovement,
    CashMovementDirection,
    CashMovementSource,
    CashMovementType,
    FixedDeposit,
    FixedDepositSettlement,
    FixedDepositStatus,
)
from debt.services import create_bank_account, create_fixed_deposit
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import fund_bank_account


def _bank(user, **overrides):
    payload = dict(
        name="Savings",
        institution_name="HDFC",
        account_number="111222333",
        currency="INR",
    )
    payload.update(overrides)
    return create_bank_account(user, **payload)


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


def _settle_payload(**overrides):
    payload = dict(
        settlement_type="MATURITY",
        settlement_date=date(2026, 1, 1),
        gross_interest=Decimal("5000"),
        tax_withheld=Decimal("500"),
    )
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_mark_matured_active_to_matured_no_cash_movement(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    movement_count_before = CashMovement.objects.count()

    response = api_client.post(f"/api/v1/fixed-deposits/{fd.id}/mark-matured")
    assert response.status_code == 200
    assert response.json()["status"] == "MATURED"
    assert CashMovement.objects.count() == movement_count_before


@pytest.mark.django_db
def test_mark_matured_on_already_matured_is_idempotent(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank, status=FixedDepositStatus.MATURED)

    response = api_client.post(f"/api/v1/fixed-deposits/{fd.id}/mark-matured")
    assert response.status_code == 200
    assert response.json()["status"] == "MATURED"


@pytest.mark.django_db
def test_mark_matured_rejects_closed(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank, status=FixedDepositStatus.CLOSED)

    response = api_client.post(f"/api/v1/fixed-deposits/{fd.id}/mark-matured")
    assert response.status_code == 400


@pytest.mark.django_db
def test_mark_matured_rejects_matured_settled(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(settlement_type="MATURITY"),
        format="json",
    )

    response = api_client.post(f"/api/v1/fixed-deposits/{fd.id}/mark-matured")
    assert response.status_code == 400


@pytest.mark.django_db
def test_settle_maturity_creates_settlement_and_movements(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank, status=FixedDepositStatus.MATURED)
    bank.refresh_from_db()
    balance_before = bank.current_balance

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["settlement_type"] == "MATURITY"
    assert body["principal_returned"] == 100000.0
    assert body["gross_interest"] == 5000.0
    assert body["tax_withheld"] == 500.0
    assert body["net_interest"] == 4500.0
    assert body["total_net_proceeds"] == 104500.0
    assert body["fixed_deposit_status"] == "MATURED_SETTLED"
    assert body["principal_cash_movement_id"] is not None
    assert body["interest_cash_movement_id"] is not None

    principal_mv = CashMovement.objects.get(id=body["principal_cash_movement_id"])
    interest_mv = CashMovement.objects.get(id=body["interest_cash_movement_id"])
    assert principal_mv.movement_type == CashMovementType.FD_MATURITY_PRINCIPAL
    assert interest_mv.movement_type == CashMovementType.FD_MATURITY_INTEREST
    assert principal_mv.direction == CashMovementDirection.CREDIT
    assert interest_mv.direction == CashMovementDirection.CREDIT
    assert principal_mv.source == CashMovementSource.SYSTEM
    assert principal_mv.linked_fixed_deposit_id == fd.id
    assert principal_mv.portfolio_id == portfolio.id

    fd.refresh_from_db()
    assert fd.status == FixedDepositStatus.MATURED_SETTLED

    bank.refresh_from_db()
    assert bank.current_balance == balance_before + Decimal("104500")


@pytest.mark.django_db
def test_settle_closure_uses_closure_movement_types(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(
            settlement_type="CLOSURE",
            gross_interest=Decimal("1000"),
            tax_withheld=Decimal("0"),
        ),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["fixed_deposit_status"] == "CLOSED"

    principal_mv = CashMovement.objects.get(id=body["principal_cash_movement_id"])
    interest_mv = CashMovement.objects.get(id=body["interest_cash_movement_id"])
    assert principal_mv.movement_type == CashMovementType.FD_CLOSURE_PRINCIPAL
    assert interest_mv.movement_type == CashMovementType.FD_CLOSURE_INTEREST


@pytest.mark.django_db
def test_settled_fd_excluded_from_portfolio_summary(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    before = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert before["current_value"] == 100000.0

    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(settlement_type="CLOSURE", gross_interest=Decimal("0"), tax_withheld=Decimal("0")),
        format="json",
    )

    after = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert after["current_value"] == 0.0
    assert after["current_value"] < before["current_value"]


@pytest.mark.django_db
def test_bank_cash_not_in_portfolio_summary_after_settlement(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    _create_fd(test_user, portfolio.id, bank)

    api_client.post(
        f"/api/v1/fixed-deposits/{FixedDeposit.objects.first().id}/settle",
        _settle_payload(),
        format="json",
    )

    summary = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert summary["current_value"] == 0.0
    bank.refresh_from_db()
    assert bank.current_balance > Decimal("100000")


@pytest.mark.django_db
def test_reject_tax_withheld_exceeds_gross(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(gross_interest=Decimal("1000"), tax_withheld=Decimal("1001")),
        format="json",
    )
    assert response.status_code == 400
    assert FixedDepositSettlement.objects.count() == 0


@pytest.mark.django_db
def test_reject_zero_proceeds(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(
            principal_returned=Decimal("0"),
            gross_interest=Decimal("0"),
            tax_withheld=Decimal("0"),
        ),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_net_interest_zero_creates_no_interest_movement(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(gross_interest=Decimal("1000"), tax_withheld=Decimal("1000")),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["net_interest"] == 0.0
    assert body["interest_cash_movement_id"] is None
    assert body["principal_cash_movement_id"] is not None
    assert (
        CashMovement.objects.filter(
            linked_fixed_deposit_id=fd.id,
            movement_type=CashMovementType.FD_MATURITY_INTEREST,
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_reject_foreign_fd(api_client, seeded, test_user, other_user):
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="INR", is_active=True
    )
    other_bank = _bank(other_user, account_number="OTHER")
    other_fd = _create_fd(other_user, other_portfolio.id, other_bank)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{other_fd.id}/settle",
        _settle_payload(),
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_reject_settle_already_settled_fd(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(settlement_type="CLOSURE", gross_interest=Decimal("0"), tax_withheld=Decimal("0")),
        format="json",
    )

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(),
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_settlement_immutable_endpoints(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    settlement_id = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(settlement_type="CLOSURE", gross_interest=Decimal("0"), tax_withheld=Decimal("0")),
        format="json",
    ).json()["id"]

    for method, path in [
        ("put", f"/api/v1/fixed-deposit-settlements/{settlement_id}"),
        ("patch", f"/api/v1/fixed-deposit-settlements/{settlement_id}"),
        ("delete", f"/api/v1/fixed-deposit-settlements/{settlement_id}"),
    ]:
        response = getattr(api_client, method)(path, {}, format="json")
        assert response.status_code == 405


@pytest.mark.django_db
def test_list_settlements_for_fd(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(settlement_type="CLOSURE", gross_interest=Decimal("0"), tax_withheld=Decimal("0")),
        format="json",
    )

    response = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/settlements")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_settlement_detail_get(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    created = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        _settle_payload(settlement_type="CLOSURE", gross_interest=Decimal("0"), tax_withheld=Decimal("0")),
        format="json",
    ).json()

    response = api_client.get(f"/api/v1/fixed-deposit-settlements/{created['id']}")
    assert response.status_code == 200
    assert response.json()["total_net_proceeds"] == 100000.0


@pytest.mark.django_db
def test_legacy_fd_without_opening_movement_can_be_settled(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = FixedDeposit.objects.create(
        user=test_user,
        portfolio=portfolio,
        bank_account=bank,
        institution_name="Legacy",
        deposit_account_number="LEG-1",
        principal_amount=Decimal("50000"),
        currency="INR",
        interest_rate_percent=Decimal("6"),
        interest_payout_frequency="ANNUALLY",
        investment_date=date(2023, 1, 1),
        maturity_date=date(2025, 1, 1),
        status=FixedDepositStatus.MATURED,
        is_active=True,
    )
    from debt.settlement_services import create_fixed_deposit_settlement

    result = create_fixed_deposit_settlement(
        test_user,
        fd.id,
        settlement_type="MATURITY",
        settlement_date=date(2025, 1, 1),
        gross_interest=Decimal("0"),
        tax_withheld=Decimal("0"),
    )
    assert result.fixed_deposit.status == FixedDepositStatus.MATURED_SETTLED
    assert result.settlement.principal_cash_movement is not None
