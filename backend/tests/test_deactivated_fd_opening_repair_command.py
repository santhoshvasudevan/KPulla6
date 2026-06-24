"""FD-ACC-10A-REPAIR: one-time repair for deactivated ledger-backed FDs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from debt.bank_ledger_services import compute_bank_account_balance
from debt.cash_ledger_flows import (
    BankCashFlowKind,
    build_bank_cash_twror_external_flows,
    classify_bank_cash_movement,
)
from debt.interest_payment_services import create_fixed_deposit_interest_payment
from debt.models import (
    CashMovement,
    CashMovementType,
    FixedDeposit,
    FixedDepositStatus,
)
from debt.repair_services import (
    RepairEligibility,
    assess_deactivated_fd_opening_repair,
    find_deactivated_fd_opening_repair_candidates,
    repair_deactivated_fd_opening_by_id,
)
from debt.services import create_bank_account, create_fixed_deposit, update_bank_account
from debt.settlement_services import create_fixed_deposit_settlement, mark_fixed_deposit_matured
from portfolios.scope import ResolvedPortfolioScope
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import fund_bank_account


def _bank(user, account_number="repair-1"):
    return create_bank_account(
        user,
        name="Savings",
        institution_name="HDFC",
        account_number=account_number,
        currency="INR",
    )


def _create_fd(user, portfolio_id, bank, **overrides):
    fund_bank_account(user, bank, "200000")
    payload = dict(
        portfolio_id=portfolio_id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number=overrides.pop("deposit_account_number", "FD-REPAIR"),
        principal_amount=Decimal(overrides.pop("principal_amount", "100000")),
        currency="INR",
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    payload.update(overrides)
    return create_fixed_deposit(user, **payload)


def _deactivate_pre_10a(fd: FixedDeposit) -> FixedDeposit:
    """Simulate legacy DELETE before FD-ACC-10A (no opening reversal)."""
    fd.is_active = False
    fd.save(update_fields=["is_active", "updated_at"])
    return fd


@pytest.mark.django_db
def test_dry_run_finds_candidate_without_changes(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    balance_before = compute_bank_account_balance(bank)
    _deactivate_pre_10a(fd)

    out = StringIO()
    call_command("repair_deactivated_fd_openings", stdout=out)
    output = out.getvalue()

    assert "[ELIGIBLE]" in output
    assert str(fd.id) in output
    assert CashMovement.objects.filter(
        movement_type=CashMovementType.FD_OPENING_REVERSAL
    ).count() == 0
    bank.refresh_from_db()
    assert compute_bank_account_balance(bank) == balance_before
    fd.refresh_from_db()
    assert fd.is_active is False
    assert fd.status != FixedDepositStatus.CANCELLED


@pytest.mark.django_db
def test_apply_creates_opening_reversal_and_restores_balance(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-apply")
    fd = _create_fd(test_user, portfolio.id, bank)
    balance_after_opening = compute_bank_account_balance(bank)
    _deactivate_pre_10a(fd)

    call_command("repair_deactivated_fd_openings", "--apply", f"--fd-id={fd.id}")

    reversal = CashMovement.objects.get(
        linked_fixed_deposit_id=fd.id,
        movement_type=CashMovementType.FD_OPENING_REVERSAL,
    )
    opening = CashMovement.objects.get(
        linked_fixed_deposit_id=fd.id,
        movement_type=CashMovementType.FD_OPENING,
    )
    assert reversal.reverses_id == opening.id
    assert reversal.is_reversal is True
    assert reversal.amount == opening.amount
    bank.refresh_from_db()
    assert compute_bank_account_balance(bank) == balance_after_opening + fd.principal_amount


@pytest.mark.django_db
def test_apply_sets_cancelled_and_keeps_inactive(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-status")
    fd = _create_fd(test_user, portfolio.id, bank)
    _deactivate_pre_10a(fd)

    call_command("repair_deactivated_fd_openings", "--apply", f"--fd-id={fd.id}")

    fd.refresh_from_db()
    assert fd.status == FixedDepositStatus.CANCELLED
    assert fd.is_active is False


@pytest.mark.django_db
def test_apply_is_idempotent(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-idem")
    fd = _create_fd(test_user, portfolio.id, bank)
    _deactivate_pre_10a(fd)

    call_command("repair_deactivated_fd_openings", "--apply", f"--fd-id={fd.id}")
    count_after_first = CashMovement.objects.filter(
        linked_fixed_deposit_id=fd.id,
        movement_type=CashMovementType.FD_OPENING_REVERSAL,
    ).count()

    out = StringIO()
    call_command(
        "repair_deactivated_fd_openings",
        "--apply",
        f"--fd-id={fd.id}",
        stdout=out,
    )
    assert count_after_first == 1
    assert "No eligible repair candidates" in out.getvalue() or "[SKIP]" in out.getvalue()


@pytest.mark.django_db
def test_skips_fd_with_interest_payments(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-int")
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
    )
    _deactivate_pre_10a(fd)

    report = assess_deactivated_fd_opening_repair(fd)
    assert report.eligibility == RepairEligibility.SKIP
    assert "interest payments" in (report.skip_reason or "").lower()

    out = StringIO()
    call_command("repair_deactivated_fd_openings", "--apply", stdout=out)
    assert CashMovement.objects.filter(
        movement_type=CashMovementType.FD_OPENING_REVERSAL,
        linked_fixed_deposit_id=fd.id,
    ).count() == 0


@pytest.mark.django_db
def test_skips_fd_with_settlement(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-settle")
    fd = _create_fd(test_user, portfolio.id, bank)
    mark_fixed_deposit_matured(test_user, fd.id)
    create_fixed_deposit_settlement(
        test_user,
        fd.id,
        settlement_type="MATURITY",
        settlement_date=date(2026, 1, 1),
        principal_returned=Decimal("100000"),
    )
    fd.refresh_from_db()
    fd.is_active = False
    fd.save(update_fields=["is_active", "updated_at"])

    report = assess_deactivated_fd_opening_repair(fd)
    assert report.eligibility == RepairEligibility.SKIP
    assert report.skip_reason is not None


@pytest.mark.django_db
def test_skips_fd_with_renewal(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-renew-old")
    old_fd = _create_fd(
        test_user,
        portfolio.id,
        bank,
        deposit_account_number="FD-OLD",
    )
    _deactivate_pre_10a(old_fd)
    _create_fd(
        test_user,
        portfolio.id,
        bank,
        deposit_account_number="FD-NEW",
        renewal_of_id=old_fd.id,
    )

    report = assess_deactivated_fd_opening_repair(old_fd)
    assert report.eligibility == RepairEligibility.SKIP
    assert "renewal" in (report.skip_reason or "").lower()


@pytest.mark.django_db
def test_skips_already_cancelled(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-cancelled")
    fd = _create_fd(test_user, portfolio.id, bank)
    _deactivate_pre_10a(fd)
    fd.status = FixedDepositStatus.CANCELLED
    fd.save(update_fields=["status", "updated_at"])

    report = assess_deactivated_fd_opening_repair(fd)
    assert report.eligibility == RepairEligibility.SKIP


@pytest.mark.django_db
def test_skips_without_fd_opening(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-no-open")
    fd = _create_fd(test_user, portfolio.id, bank, skip_opening_debit=True)
    _deactivate_pre_10a(fd)

    report = assess_deactivated_fd_opening_repair(fd)
    assert report.eligibility == RepairEligibility.SKIP


@pytest.mark.django_db
def test_fd_id_filter_limits_scan(seeded, test_user, other_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-filter-a")
    fd_a = _create_fd(test_user, portfolio.id, bank, deposit_account_number="FD-A")
    _deactivate_pre_10a(fd_a)

    other_portfolio = ensure_default_portfolio(other_user)
    other_bank = _bank(other_user, account_number="repair-filter-b")
    fd_b = _create_fd(other_user, other_portfolio.id, other_bank, deposit_account_number="FD-B")
    _deactivate_pre_10a(fd_b)

    reports = find_deactivated_fd_opening_repair_candidates(fd_id=fd_a.id)
    assert len(reports) == 1
    assert reports[0].fixed_deposit_id == fd_a.id


@pytest.mark.django_db
def test_portfolio_summary_after_repair(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-summary")
    update_bank_account(test_user, bank.id, include_in_portfolio_value=True)
    fd = _create_fd(test_user, portfolio.id, bank)
    _deactivate_pre_10a(fd)

    before = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert before["current_value"] == pytest.approx(100000.0, rel=1e-6)

    repair_deactivated_fd_opening_by_id(fd.id)

    after = api_client.get(
        "/api/v1/portfolio/summary?include_timeseries=false&display_currency=INR"
    ).json()
    assert after["current_value"] == pytest.approx(200000.0, rel=1e-6)
    fd.refresh_from_db()
    assert fd.status == FixedDepositStatus.CANCELLED


@pytest.mark.django_db
def test_repair_reversal_is_internal_not_external_flow(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, account_number="repair-flow")
    update_bank_account(test_user, bank.id, include_in_portfolio_value=True)
    fd = _create_fd(test_user, portfolio.id, bank)
    _deactivate_pre_10a(fd)

    repair_deactivated_fd_opening_by_id(fd.id)

    reversal = CashMovement.objects.get(
        linked_fixed_deposit_id=fd.id,
        movement_type=CashMovementType.FD_OPENING_REVERSAL,
    )
    assert (
        classify_bank_cash_movement(reversal, bank_included=True)
        == BankCashFlowKind.INTERNAL
    )
    scope = ResolvedPortfolioScope(kind="all_active", portfolio_ids=[portfolio.id])
    flows, unknown = build_bank_cash_twror_external_flows(
        test_user, scope, calculation_currency="INR"
    )
    assert unknown is None
    deposit_flow = sum(flows.values()) if flows else Decimal("0")
    fund_movement = CashMovement.objects.filter(
        bank_account=bank, movement_type=CashMovementType.MANUAL_DEPOSIT
    ).first()
    assert deposit_flow == fund_movement.amount
