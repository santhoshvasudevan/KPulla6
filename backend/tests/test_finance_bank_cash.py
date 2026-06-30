from datetime import date
from decimal import Decimal

import pytest

from finance.bank_cash import (
    BankCashMovementPoint,
    bank_cash_balance,
    signed_movement_amount,
)


def test_signed_movement_amount_credit_debit():
    assert signed_movement_amount(Decimal("100"), "CREDIT") == Decimal("100")
    assert signed_movement_amount(Decimal("100"), "DEBIT") == Decimal("-100")


def test_bank_cash_balance_as_of_date():
    points = [
        BankCashMovementPoint(date(2026, 1, 1), "INR", Decimal("1000"), "CREDIT"),
        BankCashMovementPoint(date(2026, 1, 5), "INR", Decimal("200"), "DEBIT"),
        BankCashMovementPoint(date(2026, 1, 10), "INR", Decimal("50"), "CREDIT"),
    ]
    assert bank_cash_balance(points) == Decimal("850")
    assert bank_cash_balance(points, as_of_date=date(2026, 1, 4)) == Decimal("1000")
    assert bank_cash_balance(points, as_of_date=date(2026, 1, 5)) == Decimal("800")


def test_bank_funding_balance_excludes_reversed_opening():
    from finance.bank_cash import BankFundingMovementPoint, bank_funding_balance

    points = [
        BankFundingMovementPoint(
            date(2023, 9, 24), "INR", Decimal("1109389"), "CREDIT"
        ),
        BankFundingMovementPoint(
            date(2023, 9, 25),
            "INR",
            Decimal("1109389"),
            "DEBIT",
            is_reversed=True,
        ),
        BankFundingMovementPoint(
            date(2026, 6, 24),
            "INR",
            Decimal("1109389"),
            "CREDIT",
            is_reversal=True,
        ),
    ]
    assert bank_funding_balance(points, as_of_date=date(2023, 9, 25)) == Decimal(
        "1109389"
    )
    assert bank_cash_balance(points, as_of_date=date(2023, 9, 25)) == Decimal("0")
