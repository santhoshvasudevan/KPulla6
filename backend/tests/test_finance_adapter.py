from datetime import date
from decimal import Decimal

import pytest

from finance.types import TransactionType
from portfolios.seed import ensure_default_portfolio
from transactions.finance_adapter import transaction_to_finance_dto
from transactions.models import Transaction


@pytest.mark.django_db
def test_transaction_to_finance_dto(seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    txn = Transaction.objects.create(
        portfolio=portfolio,
        asset_symbol="aapl",
        date=date(2026, 1, 1),
        type=TransactionType.BUY.value,
        quantity=Decimal("10.5"),
        price_per_share=Decimal("150"),
        currency="USD",
        fees=Decimal("2.5"),
    )
    dto = transaction_to_finance_dto(txn)
    assert dto.type == TransactionType.BUY
    assert dto.asset_symbol == "aapl"
    assert dto.quantity == Decimal("10.5")
    assert dto.price == Decimal("150")
    assert dto.fees == Decimal("2.5")
