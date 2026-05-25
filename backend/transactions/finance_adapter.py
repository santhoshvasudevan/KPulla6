"""Map Django Transaction rows to finance DTOs (Django allowed here, not in finance/)."""

from __future__ import annotations

from decimal import Decimal

from finance.types import Transaction, TransactionType
from transactions.models import Transaction as TransactionModel


def transaction_to_finance_dto(txn: TransactionModel) -> Transaction:
    return Transaction(
        type=TransactionType(txn.type),
        date=txn.date,
        quantity=Decimal(txn.quantity),
        price=Decimal(txn.price_per_share or 0),
        fees=Decimal(txn.fees),
        asset_symbol=txn.asset_symbol,
        split_from=Decimal(txn.split_from) if txn.split_from is not None else None,
        split_to=Decimal(txn.split_to) if txn.split_to is not None else None,
    )


def transactions_to_finance_dtos(
    txns: list[TransactionModel],
) -> list[Transaction]:
    return [transaction_to_finance_dto(t) for t in txns]
