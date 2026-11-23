"""Pure helpers for direct FD renewal proceeds allocation (#43)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_ZERO = Decimal("0")


@dataclass(frozen=True)
class RenewalAllocation:
    old_principal: Decimal
    net_interest: Decimal
    new_principal: Decimal
    cash_payout_amount: Decimal
    interest_cash_amount: Decimal
    principal_cash_amount: Decimal
    reinvested_interest_amount: Decimal
    total_available: Decimal

    @property
    def cash_received_amount(self) -> Decimal:
        return self.cash_payout_amount


def allocate_renewal_proceeds(
    *,
    old_principal: Decimal,
    net_interest: Decimal,
    new_principal: Decimal,
    cash_payout_amount: Decimal,
) -> RenewalAllocation:
    """
    Reconcile old principal + final net interest with renewed principal + bank payout.

    Interest credited to the bank is attributed first from the cash payout, with
    any remainder treated as principal returned to the bank. Reinvested interest is
    the portion of net interest not paid out.
    """
    if old_principal <= 0:
        raise ValueError("old_principal must be greater than zero.")
    if new_principal <= 0:
        raise ValueError("new_principal must be greater than zero.")
    if net_interest < 0:
        raise ValueError("net_interest must be zero or positive.")
    if cash_payout_amount < 0:
        raise ValueError("cash_payout_amount must be zero or positive.")

    total_available = old_principal + net_interest
    total_allocated = new_principal + cash_payout_amount
    if total_available != total_allocated:
        raise ValueError(
            "Inconsistent renewal allocation: "
            f"old principal ({old_principal}) + net interest ({net_interest}) "
            f"= {total_available}, but new principal ({new_principal}) + "
            f"cash payout ({cash_payout_amount}) = {total_allocated}."
        )

    interest_cash = min(net_interest, cash_payout_amount)
    principal_cash = cash_payout_amount - interest_cash
    reinvested_interest = net_interest - interest_cash
    return RenewalAllocation(
        old_principal=old_principal,
        net_interest=net_interest,
        new_principal=new_principal,
        cash_payout_amount=cash_payout_amount,
        interest_cash_amount=interest_cash,
        principal_cash_amount=principal_cash,
        reinvested_interest_amount=reinvested_interest,
        total_available=total_available,
    )
