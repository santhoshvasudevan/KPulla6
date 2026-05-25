from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction as db_transaction
from django.db.models import QuerySet

from portfolios.scope import (
    PortfolioScopeError,
    resolve_portfolio_id_or_default,
    resolve_portfolio_scope,
)
from portfolios.services import PortfolioNotFoundError
from transactions.models import Transaction, TransactionType


class TransactionNotFoundError(Exception):
    pass


class TransactionValidationError(Exception):
    pass


@dataclass
class PaginatedTransactions:
    items: list[Transaction]
    total: int
    page: int
    page_size: int
    pages: int


def _base_queryset() -> QuerySet[Transaction]:
    return Transaction.objects.select_related("portfolio").order_by("-date", "-id")


def list_transactions(
    *,
    page: int = 1,
    page_size: int = 20,
    asset_symbol: str | None = None,
    portfolio_scope: str | None = None,
    portfolio_id: int | None = None,
) -> PaginatedTransactions:
    try:
        scope = resolve_portfolio_scope(
            portfolio_scope=portfolio_scope,
            portfolio_id=portfolio_id,
        )
    except PortfolioScopeError as exc:
        raise TransactionValidationError(str(exc)) from exc
    except PortfolioNotFoundError as exc:
        raise exc

    queryset = _base_queryset()
    if scope.portfolio_ids is not None:
        if not scope.portfolio_ids:
            return PaginatedTransactions(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                pages=1 if page_size > 0 else 1,
            )
        queryset = queryset.filter(portfolio_id__in=scope.portfolio_ids)

    if asset_symbol:
        symbol = asset_symbol.strip().upper()
        queryset = queryset.filter(asset_symbol__iexact=symbol)

    total = queryset.count()
    offset = (page - 1) * page_size
    items = list(queryset[offset : offset + page_size])
    pages = (total + page_size - 1) // page_size if page_size > 0 else 1

    return PaginatedTransactions(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def get_transaction(transaction_id: int) -> Transaction:
    transaction = (
        _base_queryset().filter(pk=transaction_id).first()
    )
    if not transaction:
        raise TransactionNotFoundError("Transaction not found")
    return transaction


def create_transaction(*, validated_data: dict[str, Any]) -> Transaction:
    portfolio_id = validated_data.pop("portfolio_id", None)
    try:
        resolved_id = resolve_portfolio_id_or_default(portfolio_id)
    except PortfolioNotFoundError:
        raise

    transaction = Transaction(portfolio_id=resolved_id, **validated_data)
    transaction.save()
    return get_transaction(transaction.id)


def update_transaction(
    transaction_id: int,
    *,
    validated_data: dict[str, Any],
    update_portfolio: bool,
) -> Transaction:
    transaction = get_transaction(transaction_id)

    if update_portfolio:
        portfolio_id = validated_data.pop("portfolio_id", None)
        try:
            transaction.portfolio_id = resolve_portfolio_id_or_default(portfolio_id)
        except PortfolioNotFoundError:
            raise
    else:
        validated_data.pop("portfolio_id", None)

    for field, value in validated_data.items():
        setattr(transaction, field, value)
    transaction.save()
    return get_transaction(transaction.id)


def delete_transaction(transaction_id: int) -> None:
    transaction = get_transaction(transaction_id)
    transaction.delete()


def normalize_asset_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


@dataclass
class CsvImportResult:
    success: bool
    imported_count: int
    errors: list[dict[str, Any]]


@db_transaction.atomic
def import_transactions_from_csv(
    *,
    csv_text: str,
    portfolio_id: int | None = None,
) -> CsvImportResult:
    from transactions.csv_import import parse_transaction_csv

    payloads, parse_errors = parse_transaction_csv(csv_text)
    if parse_errors:
        return CsvImportResult(success=False, imported_count=0, errors=parse_errors)

    try:
        target_portfolio_id = resolve_portfolio_id_or_default(portfolio_id)
    except PortfolioNotFoundError:
        raise

    for data in payloads:
        validated = validate_transaction_payload(
            txn_type=data["type"],
            asset_symbol=data.get("asset_symbol"),
            date=data.get("date"),
            quantity=data.get("quantity"),
            price_per_share=data.get("price_per_share"),
            fees=data.get("fees"),
            currency=data.get("currency"),
            split_from=data.get("split_from"),
            split_to=data.get("split_to"),
        )
        Transaction.objects.create(portfolio_id=target_portfolio_id, **validated)

    return CsvImportResult(
        success=True,
        imported_count=len(payloads),
        errors=[],
    )


def validate_transaction_payload(
    *,
    txn_type: str,
    asset_symbol: str | None,
    date,
    quantity: Decimal | None,
    price_per_share: Decimal | None,
    fees: Decimal | None,
    currency: str | None,
    split_from: Decimal | None,
    split_to: Decimal | None,
) -> dict[str, Any]:
    symbol = normalize_asset_symbol(asset_symbol or "")
    if not symbol:
        raise TransactionValidationError("asset_symbol is required")
    if date is None:
        raise TransactionValidationError("date is required")

    if txn_type == TransactionType.STOCK_SPLIT:
        if split_from is None or split_to is None:
            raise TransactionValidationError(
                "split_from and split_to are required for STOCK_SPLIT"
            )
        if split_from <= 0 or split_to <= 0:
            raise TransactionValidationError(
                "split_from and split_to must be greater than 0"
            )
        return {
            "asset_symbol": symbol,
            "date": date,
            "type": txn_type,
            "quantity": Decimal("0"),
            "price_per_share": Decimal("0"),
            "fees": Decimal("0"),
            "currency": (currency or "EUR").strip().upper() or "EUR",
            "split_from": split_from,
            "split_to": split_to,
        }

    if txn_type not in TransactionType.values:
        raise TransactionValidationError(f"Unsupported transaction type: {txn_type}")

    if quantity is None or quantity <= 0:
        raise TransactionValidationError("quantity must be greater than 0")
    if price_per_share is None or price_per_share < 0:
        raise TransactionValidationError(
            "price_per_share must be greater than or equal to 0"
        )
    fee_value = Decimal("0") if fees is None else fees
    if fee_value < 0:
        raise TransactionValidationError("fees must be greater than or equal to 0")

    return {
        "asset_symbol": symbol,
        "date": date,
        "type": txn_type,
        "quantity": quantity,
        "price_per_share": price_per_share,
        "fees": fee_value,
        "currency": (currency or "EUR").strip().upper() or "EUR",
        "split_from": None,
        "split_to": None,
    }
