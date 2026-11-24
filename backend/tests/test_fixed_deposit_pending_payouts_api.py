"""#45: pending FD maturity payouts on settle/renew and confirmation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from debt import pending_payout_services, settlement_services
from debt.models import (
    CashMovement,
    CashMovementType,
    FixedDeposit,
    FixedDepositPendingPayout,
    FixedDepositRenewalGroup,
    FixedDepositSettlement,
    FixedDepositStatus,
)
from debt.pending_payout_services import confirm_fixed_deposit_pending_payout
from debt.services import create_fixed_deposit
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _create_fd(user, portfolio, bank=None, **overrides):
    if bank is None:
        bank = create_test_bank_account(user, portfolio=portfolio)
    fund_bank_account(user, bank, "200000")
    payload = dict(
        portfolio_id=portfolio.id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-001",
        principal_amount=Decimal("100000"),
        currency="INR",
        interest_rate_percent=Decimal("7.0"),
        interest_payout_frequency="COMPOUNDED",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    payload.update(overrides)
    return create_fixed_deposit(user, **payload)


def _renew_payload(**overrides):
    payload = dict(
        renewal_date="2026-01-01",
        new_deposit_account_number="FD-002",
        new_principal_amount="100000",
        new_interest_rate_percent="7.5",
        new_interest_payout_frequency="QUARTERLY",
        new_investment_date="2026-01-01",
        new_maturity_date="2028-01-01",
    )
    payload.update(overrides)
    return payload


def _settle_pending(api_client, fd, **overrides):
    payload = {
        "settlement_type": "MATURITY",
        "settlement_date": "2026-01-01",
        "gross_interest": "15000",
        "tax_withheld": "1500",
        "final_interest_pending": True,
        "pending_expected_date": "2026-01-10",
    }
    payload.update(overrides)
    return api_client.post(f"/api/v1/fixed-deposits/{fd.id}/settle", payload, format="json")


def _confirm(api_client, pending_id, **overrides):
    payload = {
        "payment_date": "2026-01-12",
        "gross_interest": "15000",
        "tax_withheld": "1500",
    }
    payload.update(overrides)
    return api_client.post(
        f"/api/v1/fixed-deposit-pending-payouts/{pending_id}/confirm",
        payload,
        format="json",
    )


def _interest_movements(fd):
    return CashMovement.objects.filter(
        linked_fixed_deposit=fd,
        movement_type__in=[
            CashMovementType.FD_MATURITY_INTEREST,
            CashMovementType.FD_CLOSURE_INTEREST,
            CashMovementType.FD_INTEREST,
        ],
    )


# --- settle ----------------------------------------------------------------


@pytest.mark.django_db
def test_settle_with_pending_credits_principal_only(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    bank = fd.bank_account
    bank.refresh_from_db()
    balance_before = bank.current_balance

    response = _settle_pending(api_client, fd)

    assert response.status_code == 201
    body = response.json()
    assert body["final_interest_pending"] is True
    assert body["gross_interest"] == 0.0
    assert body["net_interest"] == 0.0
    assert body["total_net_proceeds"] == 100000.0
    assert body["interest_cash_movement_id"] is None
    pending = body["pending_payout"]
    assert pending["status"] == "PENDING"
    assert pending["origin"] == "SETTLEMENT"
    assert pending["expected_payout_date"] == "2026-01-10"
    assert pending["suggested_gross_interest"] == 15000.0
    assert pending["suggested_tax_withheld"] == 1500.0
    assert pending["suggested_net_interest"] == 13500.0
    assert pending["cash_movement_id"] is None

    bank.refresh_from_db()
    assert bank.current_balance == balance_before + Decimal("100000")
    assert not _interest_movements(fd).exists()
    fd.refresh_from_db()
    assert fd.status == FixedDepositStatus.MATURED_SETTLED


@pytest.mark.django_db
def test_settle_pending_allows_blank_expected_date_and_no_suggestion(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)

    response = _settle_pending(
        api_client,
        fd,
        gross_interest="0",
        tax_withheld="0",
        pending_expected_date=None,
    )

    assert response.status_code == 201
    pending = response.json()["pending_payout"]
    assert pending["expected_payout_date"] is None
    assert pending["suggested_gross_interest"] is None
    assert pending["suggested_net_interest"] is None


@pytest.mark.django_db
def test_settle_without_pending_keeps_interest_credit(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        {
            "settlement_type": "MATURITY",
            "settlement_date": "2026-01-01",
            "gross_interest": "15000",
            "tax_withheld": "1500",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["final_interest_pending"] is False
    assert response.json()["pending_payout"] is None
    assert _interest_movements(fd).count() == 1
    assert not FixedDepositPendingPayout.objects.exists()


@pytest.mark.django_db
def test_settle_rejects_expected_date_without_pending(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)

    response = _settle_pending(api_client, fd, final_interest_pending=False)

    assert response.status_code == 400
    assert not FixedDepositSettlement.objects.exists()


@pytest.mark.django_db
def test_settle_pending_creation_is_atomic(api_client, seeded, test_user, monkeypatch):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    movement_count = CashMovement.objects.count()

    def boom(*args, **kwargs):
        raise pending_payout_services.PendingPayoutValidationError("forced failure")

    monkeypatch.setattr(settlement_services, "create_pending_payout", boom)
    response = _settle_pending(api_client, fd)

    assert response.status_code == 400
    fd.refresh_from_db()
    assert fd.status == FixedDepositStatus.ACTIVE
    assert not FixedDepositSettlement.objects.exists()
    assert CashMovement.objects.count() == movement_count


# --- renew -----------------------------------------------------------------


@pytest.mark.django_db
def test_renew_pending_excludes_interest_from_allocation(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    bank = fd.bank_account
    bank.refresh_from_db()
    balance_before = bank.current_balance

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(
            gross_interest="5000",
            tax_withheld="500",
            final_interest_pending=True,
        ),
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["final_interest_pending"] is True
    assert body["net_interest"] == 0.0
    assert body["interest_cash_amount"] == 0.0
    assert body["reinvested_interest_amount"] == 0.0
    assert body["cash_movement_ids"] == []
    pending = body["pending_payout"]
    assert pending["fixed_deposit_id"] == fd.id
    assert pending["origin"] == "RENEWAL"
    assert pending["suggested_net_interest"] == 4500.0
    assert pending["expected_payout_date"] is None

    group = FixedDepositRenewalGroup.objects.get(id=body["renewal_id"])
    assert group.net_interest == Decimal("0")
    assert group.total_maturity_value == Decimal("100000")
    bank.refresh_from_db()
    assert bank.current_balance == balance_before


@pytest.mark.django_db
def test_renew_pending_cannot_reinvest_estimated_interest(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    fd_count = FixedDeposit.objects.count()

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(
            new_principal_amount="104500",
            gross_interest="5000",
            tax_withheld="500",
            final_interest_pending=True,
        ),
        format="json",
    )

    assert response.status_code == 400
    assert "Inconsistent renewal allocation" in response.json()["detail"]
    assert FixedDeposit.objects.count() == fd_count
    assert not FixedDepositPendingPayout.objects.exists()
    fd.refresh_from_db()
    assert fd.status == FixedDepositStatus.ACTIVE


@pytest.mark.django_db
def test_renew_pending_cannot_pay_out_estimated_interest(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(
            cash_payout_amount="4500",
            gross_interest="5000",
            tax_withheld="500",
            final_interest_pending=True,
        ),
        format="json",
    )

    assert response.status_code == 400
    assert not FixedDepositPendingPayout.objects.exists()


@pytest.mark.django_db
def test_renew_pending_partial_principal_payout_credits_principal_only(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    bank = fd.bank_account
    bank.refresh_from_db()
    balance_before = bank.current_balance

    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(
            new_principal_amount="90000",
            cash_payout_amount="10000",
            gross_interest="5000",
            final_interest_pending=True,
            pending_expected_date="2026-01-15",
        ),
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["principal_cash_amount"] == 10000.0
    movement = CashMovement.objects.get(id=body["cash_movement_ids"][0])
    assert movement.movement_type == CashMovementType.FD_MATURITY_PRINCIPAL
    assert not _interest_movements(fd).exists()
    bank.refresh_from_db()
    assert bank.current_balance == balance_before + Decimal("10000")


# --- list / FD serializer ---------------------------------------------------


@pytest.mark.django_db
def test_fd_list_exposes_pending_payout_on_completed_term(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(gross_interest="5000", final_interest_pending=True),
        format="json",
    )

    history = api_client.get("/api/v1/fixed-deposits?lifecycle_view=history").json()
    current = api_client.get("/api/v1/fixed-deposits?lifecycle_view=current").json()

    assert history[0]["id"] == fd.id
    assert history[0]["pending_payout"]["status"] == "PENDING"
    assert history[0]["pending_payout"]["suggested_gross_interest"] == 5000.0
    assert current[0]["pending_payout"] is None


@pytest.mark.django_db
def test_pending_payout_list_is_scoped_to_owner_and_portfolio(
    api_client, seeded, test_user, other_user
):
    default_portfolio = ensure_default_portfolio(test_user)
    second = Portfolio.objects.create(
        user=test_user, name="Second", base_currency="INR", is_active=True
    )
    fd_a = _create_fd(test_user, default_portfolio)
    fd_b = _create_fd(
        test_user,
        second,
        bank=create_test_bank_account(test_user, portfolio=second, account_number="B-2"),
        deposit_account_number="FD-B",
    )
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="INR", is_active=True
    )
    other_fd = _create_fd(
        other_user,
        other_portfolio,
        bank=create_test_bank_account(other_user, portfolio=other_portfolio),
    )
    settlement_services.create_fixed_deposit_settlement(
        other_user,
        other_fd.id,
        settlement_type="MATURITY",
        settlement_date=date(2026, 1, 1),
        final_interest_pending=True,
    )
    assert _settle_pending(api_client, fd_a).status_code == 201
    assert _settle_pending(api_client, fd_b).status_code == 201

    all_items = api_client.get(
        "/api/v1/fixed-deposit-pending-payouts?portfolio_scope=all"
    ).json()
    assert {item["fixed_deposit_id"] for item in all_items} == {fd_a.id, fd_b.id}
    row = next(item for item in all_items if item["fixed_deposit_id"] == fd_b.id)
    assert row["portfolio_name"] == "Second"
    assert row["deposit_account_number"] == "FD-B"
    assert row["fixed_deposit_status"] == "MATURED_SETTLED"

    scoped = api_client.get(
        f"/api/v1/fixed-deposit-pending-payouts?portfolio_id={second.id}"
    ).json()
    assert [item["fixed_deposit_id"] for item in scoped] == [fd_b.id]

    other_pending = FixedDepositPendingPayout.objects.get(fixed_deposit=other_fd)
    assert api_client.get(
        f"/api/v1/fixed-deposit-pending-payouts/{other_pending.id}"
    ).status_code == 404


@pytest.mark.django_db
def test_pending_payout_list_status_filter(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(api_client, fd).json()["pending_payout"]["id"]
    assert _confirm(api_client, pending_id).status_code == 201

    assert api_client.get("/api/v1/fixed-deposit-pending-payouts").json() == []
    confirmed = api_client.get(
        "/api/v1/fixed-deposit-pending-payouts?status=confirmed"
    ).json()
    assert [item["id"] for item in confirmed] == [pending_id]
    assert len(api_client.get("/api/v1/fixed-deposit-pending-payouts?status=all").json()) == 1
    assert api_client.get(
        "/api/v1/fixed-deposit-pending-payouts?status=bogus"
    ).status_code == 400


# --- confirm ----------------------------------------------------------------


@pytest.mark.django_db
def test_confirm_posts_one_linked_credit_on_actual_date(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(api_client, fd).json()["pending_payout"]["id"]
    bank = fd.bank_account
    bank.refresh_from_db()
    balance_before = bank.current_balance

    response = _confirm(api_client, pending_id)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "CONFIRMED"
    assert body["payment_date"] == "2026-01-12"
    assert body["gross_interest"] == 15000.0
    assert body["tax_withheld"] == 1500.0
    assert body["net_interest"] == 13500.0
    assert body["discrepancy_status"] == "NONE"
    assert body["discrepancy_amount"] is None
    assert body["confirmed_at"] is not None

    movements = list(_interest_movements(fd))
    assert len(movements) == 1
    movement = movements[0]
    assert movement.id == body["cash_movement_id"]
    assert movement.movement_type == CashMovementType.FD_MATURITY_INTEREST
    assert movement.movement_date == date(2026, 1, 12)
    assert movement.amount == Decimal("13500")
    bank.refresh_from_db()
    assert bank.current_balance == balance_before + Decimal("13500")


@pytest.mark.django_db
def test_confirm_mismatch_opens_discrepancy_without_blocking(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(api_client, fd).json()["pending_payout"]["id"]

    response = _confirm(api_client, pending_id, gross_interest="14000", tax_withheld="1400")

    assert response.status_code == 201
    body = response.json()
    assert body["net_interest"] == 12600.0
    assert body["suggested_net_interest"] == 13500.0
    assert body["discrepancy_status"] == "OPEN"
    assert body["discrepancy_amount"] == -900.0
    assert body["resolution_comment"] is None
    assert body["resolved_at"] is None


@pytest.mark.django_db
def test_confirm_without_suggestion_has_no_discrepancy(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(
        api_client, fd, gross_interest="0", tax_withheld="0"
    ).json()["pending_payout"]["id"]

    body = _confirm(api_client, pending_id, gross_interest="9000", tax_withheld="0").json()

    assert body["discrepancy_status"] == "NONE"
    assert body["suggested_net_interest"] is None


@pytest.mark.django_db
def test_confirm_closure_uses_closure_interest_movement(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(
        api_client, fd, settlement_type="CLOSURE"
    ).json()["pending_payout"]["id"]

    body = _confirm(api_client, pending_id).json()

    movement = CashMovement.objects.get(id=body["cash_movement_id"])
    assert movement.movement_type == CashMovementType.FD_CLOSURE_INTEREST


@pytest.mark.django_db
def test_confirm_net_zero_posts_no_bank_credit(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(api_client, fd).json()["pending_payout"]["id"]

    body = _confirm(api_client, pending_id, gross_interest="100", tax_withheld="100").json()

    assert body["status"] == "CONFIRMED"
    assert body["net_interest"] == 0.0
    assert body["cash_movement_id"] is None
    assert not _interest_movements(fd).exists()


@pytest.mark.django_db
def test_confirm_retry_with_same_client_request_id_is_idempotent(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(api_client, fd).json()["pending_payout"]["id"]

    first = _confirm(api_client, pending_id, client_request_id="confirm-1")
    retry = _confirm(api_client, pending_id, client_request_id="confirm-1")

    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json()["cash_movement_id"] == first.json()["cash_movement_id"]
    assert retry.json()["client_request_id"] == "confirm-1"
    assert _interest_movements(fd).count() == 1


@pytest.mark.django_db
def test_second_confirm_without_request_id_conflicts(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(api_client, fd).json()["pending_payout"]["id"]

    assert _confirm(api_client, pending_id).status_code == 201
    second = _confirm(api_client, pending_id, gross_interest="16000")

    assert second.status_code == 409
    assert _interest_movements(fd).count() == 1
    assert FixedDepositPendingPayout.objects.get(id=pending_id).gross_interest == Decimal("15000")


@pytest.mark.django_db
def test_client_request_id_reuse_on_other_pending_rejected(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd_a = _create_fd(test_user, portfolio)
    fd_b = _create_fd(test_user, portfolio, deposit_account_number="FD-B")
    pending_a = _settle_pending(api_client, fd_a).json()["pending_payout"]["id"]
    pending_b = _settle_pending(api_client, fd_b).json()["pending_payout"]["id"]

    assert _confirm(api_client, pending_a, client_request_id="shared").status_code == 201
    response = _confirm(api_client, pending_b, client_request_id="shared")

    assert response.status_code == 400
    assert FixedDepositPendingPayout.objects.get(id=pending_b).status == "PENDING"
    assert not _interest_movements(fd_b).exists()


@pytest.mark.django_db
def test_confirm_foreign_pending_returns_404(api_client, seeded, test_user, other_user):
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="INR", is_active=True
    )
    other_fd = _create_fd(
        other_user,
        other_portfolio,
        bank=create_test_bank_account(other_user, portfolio=other_portfolio),
    )
    result = settlement_services.create_fixed_deposit_settlement(
        other_user,
        other_fd.id,
        settlement_type="MATURITY",
        settlement_date=date(2026, 1, 1),
        final_interest_pending=True,
    )

    response = _confirm(api_client, result.pending_payout.id)

    assert response.status_code == 404
    assert not _interest_movements(other_fd).exists()


@pytest.mark.django_db
def test_confirm_validates_amounts(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(api_client, fd).json()["pending_payout"]["id"]

    assert _confirm(api_client, pending_id, tax_withheld="20000").status_code == 400
    assert _confirm(api_client, pending_id, gross_interest="0").status_code == 400
    assert FixedDepositPendingPayout.objects.get(id=pending_id).status == "PENDING"


@pytest.mark.django_db
def test_confirm_is_atomic_when_later_step_fails(seeded, test_user, monkeypatch):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    result = settlement_services.create_fixed_deposit_settlement(
        test_user,
        fd.id,
        settlement_type="MATURITY",
        settlement_date=date(2026, 1, 1),
        gross_interest=Decimal("1000"),
        final_interest_pending=True,
    )

    def boom(*args, **kwargs):
        raise RuntimeError("forced failure after bank credit")

    monkeypatch.setattr(pending_payout_services, "classify_payout_discrepancy", boom)
    with pytest.raises(RuntimeError):
        confirm_fixed_deposit_pending_payout(
            test_user,
            result.pending_payout.id,
            payment_date=date(2026, 1, 5),
            gross_interest=Decimal("1000"),
        )

    assert not _interest_movements(fd).exists()
    assert FixedDepositPendingPayout.objects.get(id=result.pending_payout.id).status == "PENDING"


# --- reports ----------------------------------------------------------------


@pytest.mark.django_db
def test_interest_report_excludes_pending_and_counts_confirmed_once(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    renew = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(gross_interest="5000", tax_withheld="500", final_interest_pending=True),
        format="json",
    ).json()
    pending_id = renew["pending_payout"]["id"]

    before = api_client.get("/api/v1/reports/fixed-deposit-interest").json()
    assert before["rows"] == []
    assert before["totals"]["net_interest"] == 0.0

    _confirm(api_client, pending_id, gross_interest="5200", tax_withheld="520")
    after = api_client.get("/api/v1/reports/fixed-deposit-interest").json()

    assert len(after["rows"]) == 1
    row = after["rows"][0]
    assert row["source_type"] == "PENDING_PAYOUT"
    assert row["fixed_deposit_id"] == fd.id
    assert row["date"] == "2026-01-12"
    assert row["gross_interest"] == 5200.0
    assert row["net_interest"] == 4680.0
    assert row["discrepancy_status"] == "OPEN"
    assert after["totals"]["net_interest"] == 4680.0


@pytest.mark.django_db
def test_fd_detail_keeps_pending_estimate_outside_actual_totals(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(api_client, fd).json()["pending_payout"]["id"]

    before = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/detail").json()
    assert before["term_totals"]["actual_net_interest"] == 0.0
    assert before["pending_payout"]["status"] == "PENDING"
    assert before["pending_payout"]["suggested_net_interest"] == 13500.0

    _confirm(api_client, pending_id)
    after = api_client.get(
        f"/api/v1/fixed-deposits/{fd.id}/detail?financial_year=2025-26"
    ).json()

    assert after["term_totals"]["actual_gross_interest"] == 15000.0
    assert after["term_totals"]["actual_net_interest"] == 13500.0
    assert after["financial_year_summary"]["actual_net_interest_fy"] == 13500.0
    assert after["pending_payout"]["status"] == "CONFIRMED"
