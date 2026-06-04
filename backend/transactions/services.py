from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction as db_transaction
from django.db.models import Max, Min, QuerySet

from portfolios.models import Portfolio
from portfolios.scope import (
    PortfolioScopeError,
    resolve_portfolio_id_or_default,
    resolve_portfolio_scope,
)
from portfolios.services import PortfolioNotFoundError, list_active_portfolios
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
    return (
        Transaction.objects.select_related(
            "portfolio",
            "mutual_fund_detail",
            "mutual_fund_detail__folio",
            "mutual_fund_detail__folio__asset",
            "mutual_fund_detail__folio__asset__mutual_fund_profile",
        )
        .order_by("-date", "-id")
    )


def _normalize_symbols(
    asset_symbol: str | None,
    symbols: list[str] | None,
) -> list[str] | None:
    raw: list[str] = []
    if asset_symbol:
        raw.append(asset_symbol)
    if symbols:
        raw.extend(symbols)
    normalized = [s.strip().upper() for s in raw if s and s.strip()]
    if not normalized:
        return None
    # Preserve order while removing duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for sym in normalized:
        if sym not in seen:
            seen.add(sym)
            unique.append(sym)
    return unique


def _apply_transaction_filters(
    queryset: QuerySet[Transaction],
    *,
    asset_symbol: str | None,
    symbols: list[str] | None,
    date_from: date_type | None,
    date_to: date_type | None,
) -> QuerySet[Transaction]:
    normalized_symbols = _normalize_symbols(asset_symbol, symbols)
    if normalized_symbols:
        # asset_symbol is stored upper-cased, so an upper-cased __in is
        # effectively case-insensitive.
        queryset = queryset.filter(asset_symbol__in=normalized_symbols)
    if date_from is not None:
        queryset = queryset.filter(date__gte=date_from)
    if date_to is not None:
        queryset = queryset.filter(date__lte=date_to)
    return queryset


def list_transactions(
    user: AbstractBaseUser,
    *,
    page: int = 1,
    page_size: int = 20,
    asset_symbol: str | None = None,
    symbols: list[str] | None = None,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    portfolio_scope: str | None = None,
    portfolio_id: int | None = None,
) -> PaginatedTransactions:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise TransactionValidationError("date_from must not be after date_to")

    try:
        scope = resolve_portfolio_scope(
            user,
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

    queryset = _apply_transaction_filters(
        queryset,
        asset_symbol=asset_symbol,
        symbols=symbols,
        date_from=date_from,
        date_to=date_to,
    )

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


@dataclass
class TransactionFilterOptions:
    portfolios: list[dict[str, Any]] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    date_min: str | None = None
    date_max: str | None = None


def get_transaction_filter_options(
    user: AbstractBaseUser,
    *,
    portfolio_scope: str | None = None,
    portfolio_id: int | None = None,
) -> TransactionFilterOptions:
    """Distinct filter values for the transactions table, scoped to the
    requested portfolio selection. Portfolio options always list active real
    portfolios so the dropdown can broaden the current scope."""
    try:
        scope = resolve_portfolio_scope(
            user,
            portfolio_scope=portfolio_scope,
            portfolio_id=portfolio_id,
        )
    except PortfolioScopeError as exc:
        raise TransactionValidationError(str(exc)) from exc

    queryset = _base_queryset()
    if scope.portfolio_ids is not None:
        if not scope.portfolio_ids:
            queryset = queryset.none()
        else:
            queryset = queryset.filter(portfolio_id__in=scope.portfolio_ids)

    # Drop the base ORDER BY: Django appends ordering columns to the SELECT for
    # DISTINCT, which would otherwise break row-level distinctness.
    distinct_qs = queryset.order_by()
    symbols = sorted(
        distinct_qs.values_list("asset_symbol", flat=True).distinct()
    )
    types = sorted(
        distinct_qs.values_list("type", flat=True).distinct()
    )
    bounds = queryset.aggregate(date_min=Min("date"), date_max=Max("date"))

    portfolios = [
        {"id": p.id, "name": p.name}
        for p in list_active_portfolios(user)
    ]

    return TransactionFilterOptions(
        portfolios=portfolios,
        symbols=list(symbols),
        types=list(types),
        date_min=bounds["date_min"].isoformat() if bounds["date_min"] else None,
        date_max=bounds["date_max"].isoformat() if bounds["date_max"] else None,
    )


def get_transaction(user: AbstractBaseUser, transaction_id: int) -> Transaction:
    transaction = (
        _base_queryset()
        .filter(pk=transaction_id, portfolio__user=user)
        .first()
    )
    if not transaction:
        raise TransactionNotFoundError("Transaction not found")
    return transaction


def create_transaction(user: AbstractBaseUser, *, validated_data: dict[str, Any]) -> Transaction:
    portfolio_id = validated_data.pop("portfolio_id", None)
    try:
        resolved_id = resolve_portfolio_id_or_default(user, portfolio_id)
    except PortfolioNotFoundError:
        raise

    transaction = Transaction(portfolio_id=resolved_id, **validated_data)
    transaction.save()
    return get_transaction(user, transaction.id)


def update_transaction(
    user: AbstractBaseUser,
    transaction_id: int,
    *,
    validated_data: dict[str, Any],
    update_portfolio: bool,
) -> Transaction:
    transaction = get_transaction(user, transaction_id)

    if update_portfolio:
        portfolio_id = validated_data.pop("portfolio_id", None)
        try:
            transaction.portfolio_id = resolve_portfolio_id_or_default(user, portfolio_id)
        except PortfolioNotFoundError:
            raise
    else:
        validated_data.pop("portfolio_id", None)

    for field, value in validated_data.items():
        setattr(transaction, field, value)
    transaction.save()
    return get_transaction(user, transaction.id)


def delete_transaction(user: AbstractBaseUser, transaction_id: int) -> None:
    transaction = get_transaction(user, transaction_id)
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
    user: AbstractBaseUser,
    *,
    csv_text: str,
    portfolio_id: int | None = None,
) -> CsvImportResult:
    from transactions.csv_import import parse_import_csv
    from transactions.mutual_fund_services import create_mutual_fund_transaction

    csv_format, payloads, parse_errors = parse_import_csv(csv_text)
    if parse_errors:
        return CsvImportResult(success=False, imported_count=0, errors=parse_errors)

    try:
        target_portfolio_id = resolve_portfolio_id_or_default(user, portfolio_id)
    except PortfolioNotFoundError:
        raise

    if csv_format == "stock":
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
    elif csv_format == "mf":
        for data in payloads:
            create_mutual_fund_transaction(
                user,
                validated_data={**data, "portfolio_id": target_portfolio_id}
            )
    else:
        return CsvImportResult(
            success=False,
            imported_count=0,
            errors=[{"row": 1, "field": "headers", "message": "Unsupported CSV format"}],
        )

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
