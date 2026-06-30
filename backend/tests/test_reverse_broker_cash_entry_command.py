"""CASH-CORR-1A-HOTFIX: reverse_broker_cash_entry management command tests."""

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from cash.models import CashEntryType, CashLedgerEntry
from portfolios.models import Portfolio


def _deposit(portfolio, *, amount: str = "1109389", day: str = "2023-09-24"):
    return CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date.fromisoformat(day),
        currency="INR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal(amount),
        source_of_funds="salary",
    )


@pytest.mark.django_db
def test_reverse_command_dry_run_succeeds_and_writes_no_rows(test_user):
    portfolio = Portfolio.objects.create(
        user=test_user,
        name="IndianInvestments",
        base_currency="INR",
        is_active=True,
    )
    entry = _deposit(portfolio)
    before_count = CashLedgerEntry.objects.filter(portfolio=portfolio).count()

    out = StringIO()
    call_command(
        "reverse_broker_cash_entry",
        entry_id=entry.id,
        reason="Recorded in broker ledger by mistake",
        stdout=out,
    )
    output = out.getvalue()

    assert CashLedgerEntry.objects.filter(portfolio=portfolio).count() == before_count
    assert f"Entry #{entry.id}" in output
    assert "CASH_DEPOSIT" in output
    assert "1109389" in output
    assert "Recorded in broker ledger by mistake" in output
    assert "Broker cash balance now:" in output
    assert "Projected after reversal:" in output
    assert "Dry-run only" in output
    assert "Re-run with --apply" in output


@pytest.mark.django_db
def test_reverse_command_apply_creates_reversal_row(test_user):
    portfolio = Portfolio.objects.create(
        user=test_user,
        name="IndianInvestments",
        base_currency="INR",
        is_active=True,
    )
    entry = _deposit(portfolio, amount="500")

    out = StringIO()
    call_command(
        "reverse_broker_cash_entry",
        entry_id=entry.id,
        reason="Test apply reversal",
        apply=True,
        stdout=out,
    )
    output = out.getvalue()

    assert "Created reversal entry #" in output
    reversal = CashLedgerEntry.objects.get(is_reversal=True, reverses_id=entry.id)
    assert reversal.entry_type == CashEntryType.CASH_WITHDRAWAL
    assert reversal.amount == Decimal("-500")
    entry.refresh_from_db()
    assert entry.amount == Decimal("500")


@pytest.mark.django_db
def test_reverse_command_missing_reason_fails(test_user):
    portfolio = Portfolio.objects.create(
        user=test_user,
        name="PF",
        base_currency="INR",
        is_active=True,
    )
    entry = _deposit(portfolio, amount="100")

    with pytest.raises(CommandError, match="reason is required"):
        call_command(
            "reverse_broker_cash_entry",
            entry_id=entry.id,
            reason="   ",
            apply=True,
        )


@pytest.mark.django_db
def test_reverse_command_unknown_entry_fails():
    with pytest.raises(CommandError, match="not found"):
        call_command(
            "reverse_broker_cash_entry",
            entry_id=999999,
            reason="noop",
        )


def test_reverse_command_is_registered():
    from django.core.management import get_commands

    assert "reverse_broker_cash_entry" in get_commands()
