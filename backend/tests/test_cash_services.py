from datetime import date
from decimal import Decimal

import pytest

from cash.models import CashEntryType, CashLedgerEntry, CashTransferGroup
from cash.services import (
    CashEntryNotEditableError,
    CashValidationError,
    FutureCashImpactError,
    InsufficientCashError,
    create_cash_deposit,
    create_cash_transfer,
    create_cash_withdrawal,
    current_cash_balances,
    delete_cash_ledger_entry,
    is_manual_editable_entry,
    list_ledger_points_for_portfolio,
    update_cash_ledger_entry,
)
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from portfolios.services import PortfolioNotFoundError


@pytest.mark.django_db
def test_current_cash_balances_from_orm(test_user):
    portfolio = ensure_default_portfolio(test_user)
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 1, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("1000"),
    )
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 1, 2),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-250"),
    )
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 1, 1),
        currency="INR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("50000"),
    )
    assert current_cash_balances(portfolio) == {
        "EUR": Decimal("750"),
        "INR": Decimal("50000"),
    }
    points = list_ledger_points_for_portfolio(
        portfolio, currency="EUR", date_from=date(2026, 1, 2)
    )
    assert len(points) == 1
    assert points[0].amount == Decimal("-250")


@pytest.mark.django_db
def test_create_cash_deposit_service(test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = create_cash_deposit(
        test_user,
        portfolio_id=portfolio.id,
        entry_date="2026-06-04",
        currency="eur",
        amount=Decimal("500"),
        note="test",
    )
    assert entry.entry_type == CashEntryType.CASH_DEPOSIT
    assert entry.amount == Decimal("500")
    assert entry.currency == "EUR"


@pytest.mark.django_db
def test_create_cash_withdrawal_insufficient(test_user):
    portfolio = ensure_default_portfolio(test_user)
    create_cash_deposit(
        test_user,
        portfolio_id=portfolio.id,
        entry_date="2026-06-01",
        currency="EUR",
        amount=Decimal("100"),
    )
    with pytest.raises(InsufficientCashError) as exc_info:
        create_cash_withdrawal(
            test_user,
            portfolio_id=portfolio.id,
            entry_date="2026-06-04",
            currency="EUR",
            amount=Decimal("200"),
        )
    assert exc_info.value.shortfall == Decimal("100")


@pytest.mark.django_db
def test_create_cash_deposit_other_user_404(test_user, other_user):
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="EUR", is_active=True
    )
    with pytest.raises(PortfolioNotFoundError):
        create_cash_deposit(
            test_user,
            portfolio_id=other_portfolio.id,
            entry_date="2026-06-04",
            currency="EUR",
            amount=Decimal("1"),
        )


@pytest.mark.django_db
def test_is_manual_editable_entry():
    portfolio = Portfolio(id=1, name="P", base_currency="EUR")
    manual = CashLedgerEntry(
        portfolio=portfolio,
        date=date(2026, 1, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("1"),
    )
    assert is_manual_editable_entry(manual) is True
    linked = CashLedgerEntry(
        portfolio=portfolio,
        date=date(2026, 1, 1),
        currency="EUR",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("1"),
        linked_transaction_id=99,
    )
    assert is_manual_editable_entry(linked) is False


@pytest.mark.django_db
def test_update_and_delete_manual_deposit_service(test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = create_cash_deposit(
        test_user,
        portfolio_id=portfolio.id,
        entry_date="2026-06-01",
        currency="EUR",
        amount=Decimal("500"),
    )
    updated = update_cash_ledger_entry(
        test_user,
        entry.id,
        entry_date="2026-06-02",
        currency="EUR",
        amount=Decimal("600"),
        note="edited",
    )
    assert updated.amount == Decimal("600")
    assert updated.note == "edited"
    delete_cash_ledger_entry(test_user, entry.id)
    assert not CashLedgerEntry.objects.filter(pk=entry.id).exists()


@pytest.mark.django_db
def test_delete_deposit_blocked_negative_balance_service(test_user):
    portfolio = ensure_default_portfolio(test_user)
    deposit = create_cash_deposit(
        test_user,
        portfolio_id=portfolio.id,
        entry_date="2026-06-01",
        currency="EUR",
        amount=Decimal("1000"),
    )
    CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 10),
        currency="EUR",
        entry_type=CashEntryType.CASH_WITHDRAWAL,
        amount=Decimal("-800"),
    )
    with pytest.raises(FutureCashImpactError) as exc_info:
        delete_cash_ledger_entry(test_user, deposit.id)
    assert exc_info.value.impact.currency == "EUR"
    assert exc_info.value.impact.lowest_balance < 0


@pytest.mark.django_db
def test_delete_buy_settlement_not_editable_service(test_user):
    portfolio = ensure_default_portfolio(test_user)
    entry = CashLedgerEntry.objects.create(
        portfolio=portfolio,
        date=date(2026, 6, 1),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-10"),
    )
    with pytest.raises(CashEntryNotEditableError):
        delete_cash_ledger_entry(test_user, entry.id)


@pytest.mark.django_db
def test_create_cash_transfer_service(test_user):
    source = ensure_default_portfolio(test_user)
    target = Portfolio.objects.create(
        user=test_user, name="Target", base_currency="EUR", is_active=True
    )
    create_cash_deposit(
        test_user,
        portfolio_id=source.id,
        entry_date="2026-06-01",
        currency="EUR",
        amount=Decimal("5000"),
    )
    result = create_cash_transfer(
        test_user,
        source_portfolio_id=source.id,
        target_portfolio_id=target.id,
        entry_date="2026-06-06",
        source_currency="EUR",
        source_amount=Decimal("1000"),
        target_currency="EUR",
        target_amount=Decimal("1000"),
        note="Move cash",
    )
    assert result.source_amount == Decimal("1000")
    assert result.target_amount == Decimal("1000")
    assert result.implied_rate == Decimal("1")
    assert result.out_entry.entry_type == CashEntryType.TRANSFER_OUT
    assert result.out_entry.amount == Decimal("-1000")
    assert result.in_entry.entry_type == CashEntryType.TRANSFER_IN
    assert result.in_entry.amount == Decimal("1000")
    group = CashTransferGroup.objects.get(pk=result.transfer_group_id)
    assert group.source_currency == "EUR"
    assert group.target_currency == "EUR"
    assert group.user_rate == Decimal("1")
    assert group.fees == Decimal("0")


@pytest.mark.django_db
def test_create_cash_transfer_same_portfolio_rejected(test_user):
    portfolio = ensure_default_portfolio(test_user)
    create_cash_deposit(
        test_user,
        portfolio_id=portfolio.id,
        entry_date="2026-06-01",
        currency="EUR",
        amount=Decimal("100"),
    )
    with pytest.raises(CashValidationError):
        create_cash_transfer(
            test_user,
            source_portfolio_id=portfolio.id,
            target_portfolio_id=portfolio.id,
            entry_date="2026-06-06",
            source_currency="EUR",
            source_amount=Decimal("50"),
            target_currency="EUR",
            target_amount=Decimal("50"),
        )


@pytest.mark.django_db
def test_create_cash_transfer_future_impact_blocked(test_user):
    source = ensure_default_portfolio(test_user)
    target = Portfolio.objects.create(
        user=test_user, name="Target", base_currency="EUR", is_active=True
    )
    create_cash_deposit(
        test_user,
        portfolio_id=source.id,
        entry_date="2026-06-01",
        currency="EUR",
        amount=Decimal("1000"),
    )
    CashLedgerEntry.objects.create(
        portfolio=source,
        date=date(2026, 6, 10),
        currency="EUR",
        entry_type=CashEntryType.BUY_SETTLEMENT,
        amount=Decimal("-900"),
    )
    with pytest.raises(FutureCashImpactError):
        create_cash_transfer(
            test_user,
            source_portfolio_id=source.id,
            target_portfolio_id=target.id,
            entry_date="2026-06-05",
            source_currency="EUR",
            source_amount=Decimal("500"),
            target_currency="EUR",
            target_amount=Decimal("500"),
        )


@pytest.mark.django_db
def test_create_cross_currency_transfer_service(test_user):
    source = ensure_default_portfolio(test_user)
    target = Portfolio.objects.create(
        user=test_user, name="Target", base_currency="EUR", is_active=True
    )
    CashLedgerEntry.objects.create(
        portfolio=source,
        date=date(2026, 6, 1),
        currency="USD",
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=Decimal("2000"),
    )
    result = create_cash_transfer(
        test_user,
        source_portfolio_id=source.id,
        target_portfolio_id=target.id,
        entry_date="2026-06-06",
        source_currency="USD",
        source_amount=Decimal("1000"),
        target_currency="EUR",
        target_amount=Decimal("920"),
    )
    assert result.out_entry.currency == "USD"
    assert result.out_entry.amount == Decimal("-1000")
    assert result.in_entry.currency == "EUR"
    assert result.in_entry.amount == Decimal("920")
    assert result.implied_rate == Decimal("0.92000000")
    group = CashTransferGroup.objects.get(pk=result.transfer_group_id)
    assert group.source_currency == "USD"
    assert group.target_currency == "EUR"
    assert group.user_rate == Decimal("0.92000000")
