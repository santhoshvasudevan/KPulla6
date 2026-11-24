"""Pure renewal allocation math (#43)."""

from decimal import Decimal

import pytest

from finance.fd_renewal_allocation import allocate_renewal_proceeds


def test_full_rollover_reinvests_all_interest():
    alloc = allocate_renewal_proceeds(
        old_principal=Decimal("100000"),
        net_interest=Decimal("4500"),
        new_principal=Decimal("104500"),
        cash_payout_amount=Decimal("0"),
    )
    assert alloc.interest_cash_amount == Decimal("0")
    assert alloc.reinvested_interest_amount == Decimal("4500")
    assert alloc.principal_cash_amount == Decimal("0")


def test_principal_only_rollover_pays_interest():
    alloc = allocate_renewal_proceeds(
        old_principal=Decimal("100000"),
        net_interest=Decimal("4500"),
        new_principal=Decimal("100000"),
        cash_payout_amount=Decimal("4500"),
    )
    assert alloc.interest_cash_amount == Decimal("4500")
    assert alloc.reinvested_interest_amount == Decimal("0")


def test_partial_rollover_splits_interest():
    alloc = allocate_renewal_proceeds(
        old_principal=Decimal("100000"),
        net_interest=Decimal("4500"),
        new_principal=Decimal("102000"),
        cash_payout_amount=Decimal("2500"),
    )
    assert alloc.interest_cash_amount == Decimal("2500")
    assert alloc.reinvested_interest_amount == Decimal("2000")


def test_inconsistent_allocation_raises():
    with pytest.raises(ValueError, match="Inconsistent renewal allocation"):
        allocate_renewal_proceeds(
            old_principal=Decimal("100000"),
            net_interest=Decimal("4500"),
            new_principal=Decimal("100000"),
            cash_payout_amount=Decimal("0"),
        )
