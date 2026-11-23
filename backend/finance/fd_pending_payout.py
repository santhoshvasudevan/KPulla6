"""Pure helpers for pending FD maturity payouts (#45)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_ZERO = Decimal("0")

DISCREPANCY_NONE = "NONE"
DISCREPANCY_OPEN = "OPEN"


@dataclass(frozen=True)
class SuggestedPayout:
    gross_interest: Decimal
    tax_withheld: Decimal
    net_interest: Decimal


@dataclass(frozen=True)
class PayoutDiscrepancy:
    status: str
    amount: Decimal | None


def build_suggested_payout(
    gross_interest: Decimal | None,
    tax_withheld: Decimal | None,
) -> SuggestedPayout | None:
    """Validate a pending-payout estimate; ``None`` when no amount was provided."""
    gross = gross_interest if gross_interest is not None else _ZERO
    tax = tax_withheld if tax_withheld is not None else _ZERO
    if gross < 0:
        raise ValueError("gross_interest must be zero or positive.")
    if tax < 0:
        raise ValueError("tax_withheld must be zero or positive.")
    if tax > gross:
        raise ValueError("tax_withheld cannot exceed gross_interest.")
    if gross == 0:
        return None
    return SuggestedPayout(gross_interest=gross, tax_withheld=tax, net_interest=gross - tax)


def classify_payout_discrepancy(
    suggested_net: Decimal | None,
    actual_net: Decimal,
) -> PayoutDiscrepancy:
    """Signed ``actual - suggested`` net difference; no suggestion means no discrepancy."""
    if suggested_net is None:
        return PayoutDiscrepancy(status=DISCREPANCY_NONE, amount=None)
    delta = actual_net - suggested_net
    if delta == 0:
        return PayoutDiscrepancy(status=DISCREPANCY_NONE, amount=None)
    return PayoutDiscrepancy(status=DISCREPANCY_OPEN, amount=delta)
