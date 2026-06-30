"""CASH-UNIFY-4A: read-only cash diagnostics service and management command tests."""

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from cash.diagnostics_service import build_cash_diagnostics, cash_diagnostics_to_dict
from cash.models import CashEntryType, CashLedgerEntry
from debt.models import CashMovement, CashMovementDirection, CashMovementType
from debt.services import create_bank_account
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import fund_bank_account


@pytest.mark.django_db
def test_diagnostics_broker_and_bank_summary(test_user):
    portfolio = Portfolio.objects.create(
        user=test_user,
        name="IndianInvestments",
        base_currency="INR",
        is_active=True,
    )
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency="INR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("1500"),
    )
    bank = create_bank_account(
        test_user,
        name="HDFC NRE",
        institution_name="HDFC",
        account_number="ACC-DIAG",
        currency="INR",
        portfolio_id=portfolio.id,
    )
    fund_bank_account(test_user, bank, "25000")

    result = build_cash_diagnostics(test_user, portfolio_id=portfolio.id)
    payload = cash_diagnostics_to_dict(result)

    assert len(payload["broker_cash_by_portfolio"]) == 1
    assert payload["broker_cash_by_portfolio"][0]["balance"] == pytest.approx(1500.0)
    assert len(payload["bank_cash_by_portfolio"]) == 1
    assert payload["bank_cash_by_portfolio"][0]["balance"] == pytest.approx(25000.0)
    assert payload["unlinked_bank_accounts"] == []


@pytest.mark.django_db
def test_diagnostics_lists_unlinked_bank_account(test_user):
    bank = create_bank_account(
        test_user,
        name="External savings",
        institution_name="ICICI",
        account_number="EXT-1",
        currency="INR",
    )
    fund_bank_account(test_user, bank, "9000")

    payload = cash_diagnostics_to_dict(build_cash_diagnostics(test_user))
    assert len(payload["unlinked_bank_accounts"]) == 1
    assert payload["unlinked_bank_accounts"][0]["bank_account_id"] == bank.id
    assert payload["unlinked_bank_accounts"][0]["portfolio_assignment_status"] == "UNASSIGNED"


@pytest.mark.django_db
def test_diagnostics_flags_same_date_amount_broker_bank_pair(test_user):
    portfolio = Portfolio.objects.create(
        user=test_user,
        name="IndianInvestments",
        base_currency="INR",
        is_active=True,
    )
    bank = create_bank_account(
        test_user,
        name="HDFC NRE",
        institution_name="HDFC",
        account_number="ACC-DUP",
        currency="INR",
        portfolio_id=portfolio.id,
    )
    movement_date = date(2023, 9, 24)
    fund_bank_account(test_user, bank, "1109389", movement_date=movement_date)
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=movement_date,
        currency="INR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("1109389"),
        source_of_funds="salary",
    )

    payload = cash_diagnostics_to_dict(build_cash_diagnostics(test_user))
    assert payload["duplicate_count"] == 1
    dup = payload["possible_duplicate_entries"][0]
    assert dup["amount"] == pytest.approx(1109389.0)
    assert dup["broker_entry_type"] == CashEntryType.CASH_DEPOSIT
    assert dup["bank_account_id"] == bank.id


@pytest.mark.django_db
def test_diagnostics_is_read_only(test_user):
    portfolio = ensure_default_portfolio(test_user)
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("100"),
    )
    before_entries = CashLedgerEntry.objects.count()
    before_movements = CashMovement.objects.count()

    build_cash_diagnostics(test_user)
    out = StringIO()
    call_command("cash_overview_diagnostics", "--username", test_user.username, stdout=out)

    assert CashLedgerEntry.objects.count() == before_entries
    assert CashMovement.objects.count() == before_movements
    assert "Read-only" in out.getvalue()


@pytest.mark.django_db
def test_diagnostics_command_rejects_unknown_portfolio(test_user):
    with pytest.raises(CommandError, match="not found"):
        call_command(
            "cash_overview_diagnostics",
            "--username",
            test_user.username,
            "--portfolio-id",
            "99999",
        )
