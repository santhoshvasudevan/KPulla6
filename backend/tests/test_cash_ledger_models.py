from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from cash.constants import SUPPORTED_CASH_CURRENCIES
from cash.models import (
    CashEntryType,
    CashLedgerEntry,
    CashTransferGroup,
    validate_cash_entry_amount_sign,
)
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio


@pytest.mark.django_db
def test_new_default_portfolio_is_cash_aware_enabled(test_user):
    portfolio = ensure_default_portfolio(test_user)
    portfolio.refresh_from_db()
    assert portfolio.cash_aware_enabled is True


@pytest.mark.django_db
def test_existing_portfolio_row_keeps_false_until_updated(test_user):
    portfolio = Portfolio.objects.create(
        user=test_user,
        name="Pre Cash-4A.1",
        is_default=True,
        is_active=True,
        cash_aware_enabled=False,
    )
    assert ensure_default_portfolio(test_user).id == portfolio.id
    portfolio.refresh_from_db()
    assert portfolio.cash_aware_enabled is False


@pytest.mark.django_db
def test_cash_ledger_entry_valid_deposit(test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=date(2026, 1, 15),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("1000.00"),
    )
    entry.full_clean()
    entry.save()
    assert CashLedgerEntry.objects.filter(portfolio=portfolio).count() == 1


@pytest.mark.django_db
def test_cash_ledger_entry_zero_amount_rejected(test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=date(2026, 1, 15),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("0"),
    )
    with pytest.raises(ValidationError) as exc:
        entry.full_clean()
    assert "amount" in exc.value.error_dict


@pytest.mark.django_db
def test_cash_ledger_entry_invalid_currency_rejected(test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=date(2026, 1, 15),
        currency="XXX",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("100"),
    )
    with pytest.raises(ValidationError) as exc:
        entry.full_clean()
    assert "currency" in exc.value.error_dict


@pytest.mark.django_db
@pytest.mark.parametrize(
    "entry_type,amount",
    [
        (CashEntryType.CASH_DEPOSIT, Decimal("-100")),
        (CashEntryType.CASH_WITHDRAWAL, Decimal("100")),
        (CashEntryType.BUY_SETTLEMENT, Decimal("50")),
        (CashEntryType.SELL_SETTLEMENT, Decimal("-50")),
        (CashEntryType.TAX_WITHHELD, Decimal("50")),
    ],
)
def test_cash_ledger_entry_sign_validation(test_user, entry_type, amount):
    portfolio = ensure_default_portfolio(test_user)
    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=date(2026, 1, 15),
        currency="EUR",
        entry_type=entry_type,
        amount=amount,
    )
    with pytest.raises(ValidationError) as exc:
        entry.full_clean()
    assert "amount" in exc.value.error_dict


@pytest.mark.django_db
def test_tax_withheld_requires_negative_amount(test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=date(2026, 1, 15),
        currency="EUR",
        entry_type=CashEntryType.TAX_WITHHELD,
        amount=Decimal("-68"),
    )
    entry.full_clean()
    entry.save()


@pytest.mark.django_db
def test_cash_ledger_adjustment_allows_negative(test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=date(2026, 1, 15),
        currency="EUR",
        entry_type=CashEntryType.ADJUSTMENT,
        amount=Decimal("-25.50"),
    )
    entry.full_clean()
    entry.save()


@pytest.mark.django_db
def test_supported_cash_currency_count():
    assert len(SUPPORTED_CASH_CURRENCIES) == 20


@pytest.mark.django_db
def test_cash_transfer_group_valid(test_user, other_user):
    source = Portfolio.objects.create(
        user=test_user, name="Source", base_currency="EUR", is_active=True
    )
    target = Portfolio.objects.create(
        user=test_user, name="Target", base_currency="USD", is_active=True
    )
    group = CashTransferGroup(
        date=date(2026, 2, 1),
        source_portfolio=source,
        target_portfolio=target,
        source_currency="EUR",
        target_currency="USD",
        source_amount=Decimal("500"),
        target_amount=Decimal("540"),
        user_rate=Decimal("1.08"),
    )
    group.full_clean()
    group.save()

    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="EUR", is_active=True
    )
    bad = CashTransferGroup(
        date=date(2026, 2, 1),
        source_portfolio=source,
        target_portfolio=other_portfolio,
        source_currency="EUR",
        target_currency="USD",
        source_amount=Decimal("100"),
        target_amount=Decimal("110"),
    )
    with pytest.raises(ValidationError):
        bad.full_clean()


@pytest.mark.django_db
def test_cash_transfer_group_same_portfolio_rejected(test_user):
    portfolio = ensure_default_portfolio(test_user)
    group = CashTransferGroup(
        date=date(2026, 2, 1),
        source_portfolio=portfolio,
        target_portfolio=portfolio,
        source_currency="EUR",
        target_currency="EUR",
        source_amount=Decimal("100"),
        target_amount=Decimal("100"),
    )
    with pytest.raises(ValidationError):
        group.full_clean()


def test_validate_cash_entry_amount_sign_unit():
    validate_cash_entry_amount_sign(
        CashEntryType.CASH_DEPOSIT, Decimal("1")
    )
    with pytest.raises(ValidationError):
        validate_cash_entry_amount_sign(
            CashEntryType.BUY_SETTLEMENT, Decimal("1")
        )
