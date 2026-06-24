from datetime import date
from decimal import Decimal

import pytest

from debt.bank_ledger_services import (
    CashMovementValidationError,
    InsufficientBankBalanceError,
    OpeningBalanceAlreadySeededError,
    compute_bank_account_balance,
    create_manual_cash_movement,
    seed_opening_balance,
)
from debt.models import CashMovement, CashMovementDirection, CashMovementType
from debt.services import create_bank_account
from tests.debt_test_helpers import create_test_bank_account


def _bank(user, portfolio=None, **kwargs):
    return create_test_bank_account(user, portfolio=portfolio, **kwargs)



@pytest.mark.django_db
def test_cash_movement_model_requires_positive_amount(seeded, test_user):
    account = _bank(test_user)
    movement = CashMovement(
        user=test_user,
        bank_account=account,
        movement_type=CashMovementType.MANUAL_DEPOSIT,
        amount=Decimal("0"),
        direction=CashMovementDirection.CREDIT,
        currency="INR",
        movement_date=date(2026, 1, 1),
    )
    with pytest.raises(Exception):
        movement.save()


@pytest.mark.django_db
def test_manual_deposit_increases_current_balance(seeded, test_user):
    account = _bank(test_user)
    create_manual_cash_movement(
        test_user,
        bank_account_id=account.id,
        movement_type=CashMovementType.MANUAL_DEPOSIT,
        amount=Decimal("500"),
        movement_date=date(2026, 6, 1),
    )
    account.refresh_from_db()
    assert account.current_balance == Decimal("500")
    assert compute_bank_account_balance(account) == Decimal("500")


@pytest.mark.django_db
def test_manual_withdrawal_decreases_balance(seeded, test_user):
    account = _bank(test_user)
    create_manual_cash_movement(
        test_user,
        bank_account_id=account.id,
        movement_type=CashMovementType.MANUAL_DEPOSIT,
        amount=Decimal("1000"),
        movement_date=date(2026, 6, 1),
    )
    create_manual_cash_movement(
        test_user,
        bank_account_id=account.id,
        movement_type=CashMovementType.MANUAL_WITHDRAWAL,
        amount=Decimal("300"),
        movement_date=date(2026, 6, 2),
    )
    account.refresh_from_db()
    assert account.current_balance == Decimal("700")


@pytest.mark.django_db
def test_reject_withdrawal_overdraft(seeded, test_user):
    account = _bank(test_user)
    with pytest.raises(InsufficientBankBalanceError):
        create_manual_cash_movement(
            test_user,
            bank_account_id=account.id,
            movement_type=CashMovementType.MANUAL_WITHDRAWAL,
            amount=Decimal("100"),
            movement_date=date(2026, 6, 1),
        )


@pytest.mark.django_db
def test_reject_foreign_bank_account(seeded, test_user, other_user):
    account = _bank(other_user)
    with pytest.raises(Exception):
        create_manual_cash_movement(
            test_user,
            bank_account_id=account.id,
            movement_type=CashMovementType.MANUAL_DEPOSIT,
            amount=Decimal("100"),
            movement_date=date(2026, 6, 1),
        )


@pytest.mark.django_db
def test_reject_foreign_portfolio(seeded, test_user, other_user):
    from portfolios.models import Portfolio

    account = _bank(test_user)
    other_portfolio = Portfolio.objects.create(
        user=other_user,
        name="Other Portfolio",
        base_currency="INR",
        is_active=True,
    )
    with pytest.raises(CashMovementValidationError):
        create_manual_cash_movement(
            test_user,
            bank_account_id=account.id,
            movement_type=CashMovementType.MANUAL_DEPOSIT,
            amount=Decimal("100"),
            movement_date=date(2026, 6, 1),
            portfolio_id=other_portfolio.id,
        )


@pytest.mark.django_db
def test_seed_opening_balance_once(seeded, test_user):
    account = _bank(test_user, opening_balance=Decimal("2500"))
    movement = seed_opening_balance(test_user, account.id)
    account.refresh_from_db()
    assert movement.movement_type == CashMovementType.OPENING_BALANCE
    assert movement.amount == Decimal("2500")
    assert account.current_balance == Decimal("2500")

    with pytest.raises(OpeningBalanceAlreadySeededError):
        seed_opening_balance(test_user, account.id)


@pytest.mark.django_db
def test_seed_rejects_zero_opening_balance(seeded, test_user):
    account = _bank(test_user, opening_balance=Decimal("0"))
    with pytest.raises(CashMovementValidationError):
        seed_opening_balance(test_user, account.id)


@pytest.mark.django_db
def test_adjustment_requires_direction(seeded, test_user):
    account = _bank(test_user)
    with pytest.raises(CashMovementValidationError):
        create_manual_cash_movement(
            test_user,
            bank_account_id=account.id,
            movement_type=CashMovementType.ADJUSTMENT,
            amount=Decimal("50"),
            movement_date=date(2026, 6, 1),
        )
