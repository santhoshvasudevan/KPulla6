from decimal import Decimal

import pytest

from finance.fd_pending_payout import (
    DISCREPANCY_NONE,
    DISCREPANCY_OPEN,
    build_suggested_payout,
    classify_payout_discrepancy,
)


def test_build_suggested_payout_returns_net():
    suggestion = build_suggested_payout(Decimal("1000"), Decimal("100"))
    assert suggestion.net_interest == Decimal("900")


def test_build_suggested_payout_none_when_no_amount():
    assert build_suggested_payout(Decimal("0"), Decimal("0")) is None
    assert build_suggested_payout(None, None) is None


@pytest.mark.parametrize(
    "gross,tax",
    [(Decimal("-1"), Decimal("0")), (Decimal("10"), Decimal("-1")), (Decimal("10"), Decimal("11"))],
)
def test_build_suggested_payout_rejects_invalid(gross, tax):
    with pytest.raises(ValueError):
        build_suggested_payout(gross, tax)


def test_tax_without_gross_is_rejected():
    with pytest.raises(ValueError):
        build_suggested_payout(Decimal("0"), Decimal("5"))


def test_classify_discrepancy_none_without_suggestion():
    result = classify_payout_discrepancy(None, Decimal("500"))
    assert result.status == DISCREPANCY_NONE
    assert result.amount is None


def test_classify_discrepancy_none_when_equal():
    result = classify_payout_discrepancy(Decimal("500"), Decimal("500.0000"))
    assert result.status == DISCREPANCY_NONE


def test_classify_discrepancy_signed_actual_minus_suggested():
    assert classify_payout_discrepancy(Decimal("500"), Decimal("450")).amount == Decimal("-50")
    over = classify_payout_discrepancy(Decimal("500"), Decimal("525"))
    assert over.status == DISCREPANCY_OPEN
    assert over.amount == Decimal("25")
