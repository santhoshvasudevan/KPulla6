"""Cash ledger ORM access, scope queries, and manual deposit/withdrawal writes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction as db_transaction
from django.db.models import QuerySet

from cash.constants import SUPPORTED_CASH_CURRENCIES
from cash.models import CashEntryType, CashLedgerEntry, CashTransferGroup
from finance.cash import (
    CashLedgerPoint,
    cash_balance_by_currency,
    cash_balance_on_date,
    cash_balance_timeseries,
)
from fx.lookup import convert_amount_with_fill_from_maps, load_fx_rate_maps
from portfolios import dates as portfolio_dates
from portfolios.models import Portfolio
from portfolios.scope import ResolvedPortfolioScope, resolve_portfolio_scope
from portfolios.services import PortfolioNotFoundError, get_portfolio


class CashValidationError(Exception):
    pass


class CashEntryNotEditableError(CashValidationError):
    """Linked/system ledger rows cannot be edited or deleted."""


FUTURE_CASH_IMPACT_DETAIL = (
    "This cash change would make future cash balance negative."
)

TRANSACTION_FUTURE_CASH_IMPACT_DETAIL = (
    "This transaction change would make future cash balance negative."
)

AFFECTED_ENTRIES_LIMIT = 10


@dataclass(frozen=True)
class AffectedCashEntry:
    id: int
    date: date
    entry_type: str
    amount: Decimal
    linked_transaction_id: int | None
    asset_symbol: str | None


@dataclass(frozen=True)
class FutureCashImpact:
    currency: str
    earliest_negative_date: date
    lowest_balance: Decimal
    affected_entries: list[AffectedCashEntry]


class FutureCashImpactError(CashValidationError):
    def __init__(self, impact: FutureCashImpact) -> None:
        super().__init__(FUTURE_CASH_IMPACT_DETAIL)
        self.impact = impact


class InsufficientCashError(CashValidationError):
    def __init__(
        self,
        message: str,
        *,
        required: Decimal,
        available: Decimal,
        shortfall: Decimal,
        currency: str,
    ) -> None:
        super().__init__(message)
        self.required = required
        self.available = available
        self.shortfall = shortfall
        self.currency = currency


MANUAL_EDITABLE_ENTRY_TYPES = frozenset(
    {
        CashEntryType.CASH_DEPOSIT,
        CashEntryType.CASH_WITHDRAWAL,
    }
)


@dataclass(frozen=True)
class CashBalanceRow:
    portfolio_id: int
    portfolio_name: str
    currency: str
    balance: Decimal


@dataclass(frozen=True)
class CashBalancesAllResult:
    kind: Literal["all"]
    as_of_date: date
    balances: list[CashBalanceRow]
    totals_by_currency: list[tuple[str, Decimal]]


@dataclass(frozen=True)
class CashBalancesSingleResult:
    kind: Literal["single"]
    portfolio_id: int
    portfolio_name: str
    as_of_date: date
    balances: list[tuple[str, Decimal]]


@dataclass(frozen=True)
class CashTransferResult:
    transfer_group_id: int
    date: date
    source_portfolio_id: int
    target_portfolio_id: int
    source_currency: str
    source_amount: Decimal
    target_currency: str
    target_amount: Decimal
    implied_rate: Decimal | None
    out_entry: CashLedgerEntry
    in_entry: CashLedgerEntry


@dataclass(frozen=True)
class CashLedgerListResult:
    items: list[CashLedgerEntry]
    total: int
    page: int
    page_size: int
    pages: int


def validate_cash_currency(currency: str) -> str:
    code = (currency or "").strip().upper()
    if code not in SUPPORTED_CASH_CURRENCIES:
        raise CashValidationError(f"Unsupported cash currency: {currency}")
    return code


def parse_ledger_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            raise CashValidationError(
                f"Invalid date '{value}'. Use YYYY-MM-DD."
            ) from None
    raise CashValidationError("date is required")


def parse_positive_request_amount(value) -> Decimal:
    if value is None:
        raise CashValidationError("amount is required")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise CashValidationError("amount must be a number") from None
    if amount <= 0:
        raise CashValidationError("amount must be positive")
    return amount


def compute_implied_transfer_rate(
    source_amount: Decimal, target_amount: Decimal
) -> Decimal | None:
    if source_amount <= 0:
        return None
    return (target_amount / source_amount).quantize(Decimal("0.00000001"))


def parse_transfer_amounts(
    *,
    currency: str | None = None,
    amount=None,
    source_currency: str | None = None,
    source_amount=None,
    target_currency: str | None = None,
    target_amount=None,
) -> tuple[str, Decimal, str, Decimal]:
    """
    Normalize legacy same-currency (currency+amount) or explicit cross-currency fields.
    """
    has_legacy = currency is not None or amount is not None
    has_explicit = any(
        v is not None
        for v in (source_currency, source_amount, target_currency, target_amount)
    )
    if has_legacy and has_explicit:
        raise CashValidationError(
            "Provide either currency+amount or source/target currency amounts, not both."
        )
    if has_legacy:
        if currency is None or amount is None:
            raise CashValidationError(
                "Both currency and amount are required for same-currency transfer."
            )
        ccy = validate_cash_currency(currency)
        amt = parse_positive_request_amount(amount)
        return ccy, amt, ccy, amt
    if not has_explicit:
        raise CashValidationError(
            "Provide currency+amount or source/target currency amounts."
        )
    missing = [
        name
        for name, value in (
            ("source_currency", source_currency),
            ("source_amount", source_amount),
            ("target_currency", target_currency),
            ("target_amount", target_amount),
        )
        if value is None
    ]
    if missing:
        raise CashValidationError(
            f"Missing required transfer fields: {', '.join(missing)}."
        )
    src_ccy = validate_cash_currency(source_currency)
    tgt_ccy = validate_cash_currency(target_currency)
    src_amt = parse_positive_request_amount(source_amount)
    tgt_amt = parse_positive_request_amount(target_amount)
    if src_ccy == tgt_ccy and src_amt != tgt_amt:
        raise CashValidationError(
            "Same-currency transfer requires source_amount equal to target_amount."
        )
    return src_ccy, src_amt, tgt_ccy, tgt_amt


def _portfolio_for_cash_write(user: AbstractBaseUser, portfolio_id: int) -> Portfolio:
    scope = resolve_portfolio_scope(user, portfolio_id=portfolio_id)
    return Portfolio.objects.get(pk=scope.portfolio_ids[0])


def _active_portfolio_for_transfer(
    user: AbstractBaseUser, portfolio_id: int, *, label: str
) -> Portfolio:
    portfolio = get_portfolio(user, portfolio_id)
    if not portfolio.is_active:
        raise CashValidationError(f"{label} portfolio is inactive.")
    return portfolio


def _reload_ledger_entry(entry_id: int) -> CashLedgerEntry:
    return (
        CashLedgerEntry.objects.select_related(
            "portfolio",
            "linked_transaction",
            "linked_transaction__mutual_fund_detail",
            "linked_transaction__mutual_fund_detail__folio",
            "transfer_group",
            "transfer_group__source_portfolio",
            "transfer_group__target_portfolio",
        )
        .get(pk=entry_id)
    )


def is_manual_editable_entry(entry: CashLedgerEntry) -> bool:
    return (
        entry.entry_type in MANUAL_EDITABLE_ENTRY_TYPES
        and entry.linked_transaction_id is None
        and entry.transfer_group_id is None
    )


def _ledger_entry_for_user(user: AbstractBaseUser, entry_id: int) -> CashLedgerEntry:
    entry = (
        CashLedgerEntry.objects.select_related("portfolio")
        .filter(pk=entry_id, portfolio__user=user)
        .first()
    )
    if entry is None:
        raise PortfolioNotFoundError(f"Cash ledger entry {entry_id} not found.")
    return entry


def _require_manual_editable(entry: CashLedgerEntry) -> None:
    if not is_manual_editable_entry(entry):
        raise CashEntryNotEditableError(
            "Linked or system-generated cash entries cannot be edited directly."
        )


def future_cash_impact_payload(
    impact: FutureCashImpact,
    *,
    detail: str | None = None,
) -> dict:
    return {
        "detail": detail or FUTURE_CASH_IMPACT_DETAIL,
        "currency": impact.currency,
        "earliest_negative_date": impact.earliest_negative_date.isoformat(),
        "lowest_balance": float(impact.lowest_balance),
        "affected_entries": [
            {
                "id": row.id,
                "date": row.date.isoformat(),
                "entry_type": row.entry_type,
                "amount": float(row.amount),
                "linked_transaction_id": row.linked_transaction_id,
                "asset_symbol": row.asset_symbol,
            }
            for row in impact.affected_entries
        ],
    }


def _collect_affected_entries(
    portfolio: Portfolio,
    currency: str,
    earliest_negative_date: date,
    *,
    exclude_entry_id: int | None,
) -> list[AffectedCashEntry]:
    qs = (
        CashLedgerEntry.objects.filter(
            portfolio=portfolio,
            currency=currency,
            date__gte=earliest_negative_date,
        )
        .select_related("linked_transaction")
        .order_by("date", "id")
    )
    if exclude_entry_id is not None:
        qs = qs.exclude(pk=exclude_entry_id)
    rows: list[AffectedCashEntry] = []
    for entry in qs[:AFFECTED_ENTRIES_LIMIT]:
        asset_symbol = None
        if entry.linked_transaction_id is not None and entry.linked_transaction:
            asset_symbol = entry.linked_transaction.asset_symbol
        rows.append(
            AffectedCashEntry(
                id=entry.id,
                date=entry.date,
                entry_type=entry.entry_type,
                amount=entry.amount,
                linked_transaction_id=entry.linked_transaction_id,
                asset_symbol=asset_symbol,
            )
        )
    return rows


def analyze_future_cash_impact(
    portfolio: Portfolio,
    currency: str,
    *,
    exclude_entry_id: int | None = None,
    proposed_point: CashLedgerPoint | None = None,
    from_date: date,
) -> FutureCashImpact | None:
    """
    Simulate ledger balances in ``currency`` after a proposed manual edit/delete.

    Returns impact details when any day on or after ``from_date`` would have a
    negative running balance; otherwise None.
    """
    ccy = validate_cash_currency(currency)
    points = _ledger_points_for_currency(
        portfolio,
        ccy,
        exclude_entry_id=exclude_entry_id,
        include_point=proposed_point,
    )
    if not points:
        return None

    dates = [p.date for p in points]
    start = min(from_date, min(dates))
    end = max(dates)
    series = cash_balance_timeseries(points, start, end)
    day_balances = series.get(ccy, [])
    if not day_balances:
        return None

    earliest_negative: date | None = None
    lowest = Decimal("0")
    for day, balance in day_balances:
        if day < from_date:
            continue
        if balance < lowest:
            lowest = balance
        if balance < 0 and earliest_negative is None:
            earliest_negative = day

    if earliest_negative is None:
        return None

    affected = _collect_affected_entries(
        portfolio,
        ccy,
        earliest_negative,
        exclude_entry_id=exclude_entry_id,
    )
    return FutureCashImpact(
        currency=ccy,
        earliest_negative_date=earliest_negative,
        lowest_balance=lowest,
        affected_entries=affected,
    )


def _ledger_points_for_currency(
    portfolio: Portfolio,
    currency: str,
    *,
    exclude_entry_id: int | None = None,
    exclude_entry_ids: set[int] | None = None,
    include_point: CashLedgerPoint | None = None,
) -> list[CashLedgerPoint]:
    excluded = set(exclude_entry_ids or ())
    if exclude_entry_id is not None:
        excluded.add(exclude_entry_id)
    points: list[CashLedgerPoint] = []
    for row in ledger_entries_queryset(portfolio, currency=currency):
        if row.pk in excluded:
            continue
        points.append(ledger_entry_to_point(row))
    if include_point is not None:
        points.append(include_point)
    return points


def validate_non_negative_cash_after_change(
    portfolio: Portfolio,
    currency: str,
    *,
    exclude_entry_id: int | None = None,
    proposed_point: CashLedgerPoint | None = None,
    from_date: date,
) -> None:
    """
    Ensure running balance in ``currency`` is never negative on any day >= ``from_date``.

    Used after a proposed manual entry update or delete.
    """
    impact = analyze_future_cash_impact(
        portfolio,
        currency,
        exclude_entry_id=exclude_entry_id,
        proposed_point=proposed_point,
        from_date=from_date,
    )
    if impact is not None:
        raise FutureCashImpactError(impact)


def assert_sufficient_cash_for_purchase(
    portfolio: Portfolio,
    currency: str,
    required: Decimal,
    as_of_date: date,
    *,
    exclude_entry_id: int | None = None,
) -> None:
    """Raise ``InsufficientCashError`` when buy settlement cannot be funded."""
    if required <= 0:
        return
    ccy = validate_cash_currency(currency)
    points = _ledger_points_for_currency(
        portfolio, ccy, exclude_entry_id=exclude_entry_id
    )
    available = (
        cash_balance_on_date(points, as_of_date).get(ccy, Decimal("0"))
        if points
        else Decimal("0")
    )
    if available < required:
        raise InsufficientCashError(
            "Insufficient cash balance for purchase.",
            required=required,
            available=available,
            shortfall=required - available,
            currency=ccy,
        )


def assert_delete_settlement_would_not_make_cash_negative(
    entry: CashLedgerEntry,
) -> None:
    """Block deleting a settlement that would drive later balances negative."""
    assert_delete_entries_would_not_make_cash_negative([entry])


def assert_delete_entries_would_not_make_cash_negative(
    entries: list[CashLedgerEntry],
) -> None:
    """Block deleting linked settlements when net removal would drive balances negative."""
    if not entries:
        return
    portfolio = entries[0].portfolio
    currency = entries[0].currency
    from_date = min(entry.date for entry in entries)
    exclude_ids = {entry.id for entry in entries}
    points = _ledger_points_for_currency(
        portfolio,
        currency,
        exclude_entry_ids=exclude_ids,
    )
    if not points:
        return
    dates = [p.date for p in points]
    start = min(from_date, min(dates))
    end = max(dates)
    series = cash_balance_timeseries(points, start, end)
    day_balances = series.get(currency, [])
    for day, balance in day_balances:
        if day < from_date:
            continue
        if balance < 0:
            earliest_negative = day
            lowest = balance
            for d, bal in day_balances:
                if d < from_date:
                    continue
                if bal < lowest:
                    lowest = bal
            affected = _collect_affected_entries(
                portfolio,
                currency,
                earliest_negative,
                exclude_entry_id=None,
            )
            raise FutureCashImpactError(
                FutureCashImpact(
                    currency=currency,
                    earliest_negative_date=earliest_negative,
                    lowest_balance=lowest,
                    affected_entries=affected,
                )
            )


def _withdrawal_available_on_date(
    portfolio: Portfolio,
    currency: str,
    as_of_date: date,
    *,
    exclude_entry_id: int,
) -> Decimal:
    points = _ledger_points_for_currency(
        portfolio, currency, exclude_entry_id=exclude_entry_id
    )
    return cash_balance_on_date(points, as_of_date).get(currency, Decimal("0"))


@db_transaction.atomic
def create_cash_deposit(
    user: AbstractBaseUser,
    *,
    portfolio_id: int,
    entry_date: date | str,
    currency: str,
    amount,
    source_of_funds: str = "",
    note: str = "",
) -> CashLedgerEntry:
    portfolio = _portfolio_for_cash_write(user, portfolio_id)
    parsed_date = parse_ledger_date(entry_date)
    ccy = validate_cash_currency(currency)
    signed_amount = parse_positive_request_amount(amount)

    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=parsed_date,
        currency=ccy,
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=signed_amount,
        source_of_funds=(source_of_funds or "").strip(),
        note=(note or "").strip(),
    )
    entry.full_clean()
    entry.save()
    return _reload_ledger_entry(entry.id)


@db_transaction.atomic
def create_cash_withdrawal(
    user: AbstractBaseUser,
    *,
    portfolio_id: int,
    entry_date: date | str,
    currency: str,
    amount,
    source_of_funds: str = "",
    note: str = "",
) -> CashLedgerEntry:
    portfolio = _portfolio_for_cash_write(user, portfolio_id)
    parsed_date = parse_ledger_date(entry_date)
    ccy = validate_cash_currency(currency)
    requested = parse_positive_request_amount(amount)

    points = list_ledger_points_for_portfolio(
        portfolio, currency=ccy, as_of_date=parsed_date
    )
    available = (
        cash_balance_on_date(points, parsed_date).get(ccy, Decimal("0"))
        if points
        else Decimal("0")
    )
    if available < requested:
        raise InsufficientCashError(
            "Insufficient cash balance for withdrawal.",
            required=requested,
            available=available,
            shortfall=requested - available,
            currency=ccy,
        )

    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=parsed_date,
        currency=ccy,
        entry_type=CashEntryType.CASH_WITHDRAWAL,
        amount=-requested,
        source_of_funds=(source_of_funds or "").strip(),
        note=(note or "").strip(),
    )
    entry.full_clean()
    entry.save()
    return _reload_ledger_entry(entry.id)


@db_transaction.atomic
def create_cash_transfer(
    user: AbstractBaseUser,
    *,
    source_portfolio_id: int,
    target_portfolio_id: int,
    entry_date: date | str,
    source_currency: str,
    source_amount,
    target_currency: str,
    target_amount,
    note: str = "",
) -> CashTransferResult:
    src_ccy = validate_cash_currency(source_currency)
    tgt_ccy = validate_cash_currency(target_currency)
    src_amt = parse_positive_request_amount(source_amount)
    tgt_amt = parse_positive_request_amount(target_amount)
    if src_ccy == tgt_ccy and src_amt != tgt_amt:
        raise CashValidationError(
            "Same-currency transfer requires source_amount equal to target_amount."
        )

    if source_portfolio_id == target_portfolio_id:
        raise CashValidationError("Source and target portfolios must be different.")

    source = _active_portfolio_for_transfer(
        user, source_portfolio_id, label="Source"
    )
    target = _active_portfolio_for_transfer(
        user, target_portfolio_id, label="Target"
    )

    parsed_date = parse_ledger_date(entry_date)
    note_text = (note or "").strip()
    implied_rate = compute_implied_transfer_rate(src_amt, tgt_amt)
    user_rate = (
        Decimal("1")
        if src_ccy == tgt_ccy
        else implied_rate
    )

    points = list_ledger_points_for_portfolio(
        source, currency=src_ccy, as_of_date=parsed_date
    )
    available = (
        cash_balance_on_date(points, parsed_date).get(src_ccy, Decimal("0"))
        if points
        else Decimal("0")
    )
    if available < src_amt:
        raise InsufficientCashError(
            "Insufficient cash balance for transfer.",
            required=src_amt,
            available=available,
            shortfall=src_amt - available,
            currency=src_ccy,
        )

    proposed = CashLedgerPoint(
        date=parsed_date, currency=src_ccy, amount=-src_amt
    )
    validate_non_negative_cash_after_change(
        source,
        src_ccy,
        proposed_point=proposed,
        from_date=parsed_date,
    )

    group = CashTransferGroup(
        date=parsed_date,
        source_portfolio=source,
        target_portfolio=target,
        source_currency=src_ccy,
        target_currency=tgt_ccy,
        source_amount=src_amt,
        target_amount=tgt_amt,
        user_rate=user_rate,
        fees=Decimal("0"),
        note=note_text,
    )
    group.full_clean()
    group.save()

    out_entry = CashLedgerEntry(
        portfolio=source,
        date=parsed_date,
        currency=src_ccy,
        entry_type=CashEntryType.TRANSFER_OUT,
        amount=-src_amt,
        transfer_group=group,
        note=note_text,
    )
    in_entry = CashLedgerEntry(
        portfolio=target,
        date=parsed_date,
        currency=tgt_ccy,
        entry_type=CashEntryType.TRANSFER_IN,
        amount=tgt_amt,
        transfer_group=group,
        note=note_text,
    )
    out_entry.full_clean()
    in_entry.full_clean()
    out_entry.save()
    in_entry.save()

    return CashTransferResult(
        transfer_group_id=group.id,
        date=parsed_date,
        source_portfolio_id=source.id,
        target_portfolio_id=target.id,
        source_currency=src_ccy,
        source_amount=src_amt,
        target_currency=tgt_ccy,
        target_amount=tgt_amt,
        implied_rate=implied_rate,
        out_entry=_reload_ledger_entry(out_entry.id),
        in_entry=_reload_ledger_entry(in_entry.id),
    )


def cash_transfer_response_payload(result: CashTransferResult) -> dict:
    from cash.serializers import CashLedgerEntrySerializer

    payload = {
        "transfer_group_id": result.transfer_group_id,
        "date": result.date.isoformat(),
        "source_portfolio_id": result.source_portfolio_id,
        "target_portfolio_id": result.target_portfolio_id,
        "source_currency": result.source_currency,
        "source_amount": float(result.source_amount),
        "target_currency": result.target_currency,
        "target_amount": float(result.target_amount),
        "implied_rate": (
            float(result.implied_rate) if result.implied_rate is not None else None
        ),
        "entries": CashLedgerEntrySerializer(
            [result.out_entry, result.in_entry], many=True
        ).data,
    }
    if result.source_currency == result.target_currency:
        payload["currency"] = result.source_currency
        payload["amount"] = float(result.source_amount)
    return payload


def validate_entry_type(entry_type: str) -> str:
    code = (entry_type or "").strip().upper()
    valid = {choice.value for choice in CashEntryType}
    if code not in valid:
        raise CashValidationError(f"Unsupported entry_type: {entry_type}")
    return code


def ledger_entry_to_point(entry: CashLedgerEntry) -> CashLedgerPoint:
    return CashLedgerPoint(
        date=entry.date,
        currency=entry.currency,
        amount=entry.amount,
    )


def ledger_entries_queryset(
    portfolio: Portfolio,
    *,
    currency: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> QuerySet[CashLedgerEntry]:
    qs = CashLedgerEntry.objects.filter(portfolio=portfolio).order_by("date", "id")
    if currency is not None:
        qs = qs.filter(currency=currency)
    if date_from is not None:
        qs = qs.filter(date__gte=date_from)
    if date_to is not None:
        qs = qs.filter(date__lte=date_to)
    return qs


def list_ledger_points_for_portfolio(
    portfolio: Portfolio,
    *,
    currency: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    as_of_date: date | None = None,
) -> list[CashLedgerPoint]:
    effective_to = date_to
    if as_of_date is not None:
        effective_to = (
            min(date_to, as_of_date) if date_to is not None else as_of_date
        )
    return [
        ledger_entry_to_point(row)
        for row in ledger_entries_queryset(
            portfolio,
            currency=currency,
            date_from=date_from,
            date_to=effective_to,
        )
    ]


def current_cash_balances(
    portfolio: Portfolio,
    *,
    as_of_date: date | None = None,
    currency: str | None = None,
) -> dict[str, Decimal]:
    """Native-currency balances; only currencies with at least one ledger row in scope."""
    points = list_ledger_points_for_portfolio(
        portfolio, currency=currency, as_of_date=as_of_date
    )
    if not points:
        return {}
    if as_of_date is None:
        return cash_balance_by_currency(points)
    return cash_balance_on_date(points, as_of_date)


def _portfolio_map(portfolio_ids: list[int]) -> dict[int, Portfolio]:
    if not portfolio_ids:
        return {}
    rows = Portfolio.objects.filter(pk__in=portfolio_ids)
    return {p.id: p for p in rows}


def _entries_for_scope(
    scope: ResolvedPortfolioScope,
    *,
    currency: str | None = None,
    as_of_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    entry_type: str | None = None,
) -> list[CashLedgerEntry]:
    if not scope.portfolio_ids:
        return []
    qs = CashLedgerEntry.objects.filter(
        portfolio_id__in=scope.portfolio_ids
    ).select_related("portfolio")
    if currency is not None:
        qs = qs.filter(currency=currency)
    if entry_type is not None:
        qs = qs.filter(entry_type=entry_type)
    if date_from is not None:
        qs = qs.filter(date__gte=date_from)
    if date_to is not None:
        qs = qs.filter(date__lte=date_to)
    if as_of_date is not None:
        qs = qs.filter(date__lte=as_of_date)
    return list(qs.order_by("portfolio_id", "date", "id"))


def cash_balances_for_scope(
    scope: ResolvedPortfolioScope,
    *,
    as_of_date: date | None = None,
    currency: str | None = None,
) -> CashBalancesAllResult | CashBalancesSingleResult:
    """
    Balances in native currency only.

    Omits (portfolio, currency) pairs with no ledger rows in scope. Zero balances
    are included when ledger activity exists for that pair.
    """
    effective_as_of = as_of_date or date.today()
    entries = _entries_for_scope(
        scope, currency=currency, as_of_date=effective_as_of
    )
    portfolios = _portfolio_map(scope.portfolio_ids)

    by_portfolio_currency: dict[tuple[int, str], list[CashLedgerPoint]] = {}
    for entry in entries:
        key = (entry.portfolio_id, entry.currency)
        by_portfolio_currency.setdefault(key, []).append(ledger_entry_to_point(entry))

    rows: list[CashBalanceRow] = []
    for (pid, ccy), points in sorted(by_portfolio_currency.items()):
        portfolio = portfolios.get(pid)
        if portfolio is None:
            continue
        balance = cash_balance_on_date(points, effective_as_of).get(ccy, Decimal("0"))
        rows.append(
            CashBalanceRow(
                portfolio_id=pid,
                portfolio_name=portfolio.name,
                currency=ccy,
                balance=balance,
            )
        )

    totals: dict[str, Decimal] = {}
    for row in rows:
        totals[row.currency] = totals.get(row.currency, Decimal("0")) + row.balance
    totals_list = sorted(totals.items(), key=lambda x: x[0])

    if scope.kind == "single":
        pid = scope.portfolio_ids[0]
        portfolio = portfolios[pid]
        per_ccy = [
            (row.currency, row.balance)
            for row in rows
            if row.portfolio_id == pid
        ]
        return CashBalancesSingleResult(
            kind="single",
            portfolio_id=pid,
            portfolio_name=portfolio.name,
            as_of_date=effective_as_of,
            balances=per_ccy,
        )

    return CashBalancesAllResult(
        kind="all",
        as_of_date=effective_as_of,
        balances=rows,
        totals_by_currency=totals_list,
    )


CASH_FX_PARTIAL_WARNING = (
    "FX unavailable for one or more cash balances; portfolio value may be partial."
)

CASH_FX_VALUE_HISTORY_WARNING = (
    "FX unavailable for one or more cash balances; value history may be partial."
)

FX_LOOKBACK_DAYS = 7


@dataclass(frozen=True)
class CashDisplayBalanceRow:
    portfolio_id: int
    portfolio_name: str
    currency: str
    native_balance: Decimal
    display_value: Decimal | None
    fx_status: str


@dataclass(frozen=True)
class CashDisplaySummary:
    display_currency: str
    as_of_date: date
    balances: list[CashDisplayBalanceRow]
    totals_by_currency: list[tuple[str, Decimal]]
    display_value_by_currency: dict[str, Decimal | None]
    total_display_value: Decimal
    fx_status: str
    warnings: list[str]


def _norm_display_currency(value: str) -> str:
    return (value or "EUR").strip().upper() or "EUR"


def _combine_cash_fx_status(statuses: list[str]) -> str:
    if any(s == "fx_unavailable" for s in statuses):
        return "fx_unavailable"
    if any(s == "filled" for s in statuses):
        return "filled"
    return "ok"


def build_cash_display_summary(
    scope: ResolvedPortfolioScope,
    display_currency: str,
    *,
    as_of_date: date | None = None,
) -> CashDisplaySummary:
    """
    Native cash balances for ``scope``, converted to ``display_currency`` for summary/allocation.

    Missing FX excludes that currency from ``total_display_value`` (partial total + warning).
    Independent of ``Portfolio.cash_aware_enabled`` — ledger rows are real balances.
    """
    disp_ccy = _norm_display_currency(display_currency)
    effective_as_of = as_of_date or portfolio_dates.current_date()

    raw = cash_balances_for_scope(scope, as_of_date=effective_as_of)
    if isinstance(raw, CashBalancesSingleResult):
        portfolio_rows = [
            CashBalanceRow(
                portfolio_id=raw.portfolio_id,
                portfolio_name=raw.portfolio_name,
                currency=ccy,
                balance=bal,
            )
            for ccy, bal in raw.balances
        ]
        totals_by_currency = sorted(raw.balances, key=lambda x: x[0])
    else:
        portfolio_rows = list(raw.balances)
        totals_by_currency = list(raw.totals_by_currency)

    if not portfolio_rows:
        return CashDisplaySummary(
            display_currency=disp_ccy,
            as_of_date=effective_as_of,
            balances=[],
            totals_by_currency=[],
            display_value_by_currency={},
            total_display_value=Decimal("0"),
            fx_status="ok",
            warnings=[],
        )

    fx_pairs: set[tuple[str, str]] = set()
    for ccy, _ in totals_by_currency:
        if ccy != disp_ccy:
            fx_pairs.add((ccy, disp_ccy))
    fx_start = effective_as_of - timedelta(days=FX_LOOKBACK_DAYS)
    fx_maps = load_fx_rate_maps(fx_pairs, fx_start, effective_as_of)

    per_portfolio_display: list[CashDisplayBalanceRow] = []
    per_portfolio_statuses: list[str] = []
    for row in portfolio_rows:
        if row.balance == 0:
            converted = Decimal("0")
            st = "ok"
        elif row.currency == disp_ccy:
            converted = row.balance
            st = "ok"
        else:
            converted, st = convert_amount_with_fill_from_maps(
                row.balance,
                row.currency,
                disp_ccy,
                effective_as_of,
                fx_maps,
            )
        per_portfolio_statuses.append(st)
        per_portfolio_display.append(
            CashDisplayBalanceRow(
                portfolio_id=row.portfolio_id,
                portfolio_name=row.portfolio_name,
                currency=row.currency,
                native_balance=row.balance,
                display_value=converted,
                fx_status=st,
            )
        )

    currency_totals: dict[str, Decimal] = {}
    for ccy, bal in totals_by_currency:
        currency_totals[ccy] = currency_totals.get(ccy, Decimal("0")) + bal

    total_display = Decimal("0")
    convert_statuses: list[str] = []
    display_value_by_currency: dict[str, Decimal | None] = {}
    any_fx_missing = False
    for ccy, native_total in sorted(currency_totals.items()):
        if native_total == 0:
            display_value_by_currency[ccy] = Decimal("0")
            continue
        if ccy == disp_ccy:
            display_value_by_currency[ccy] = native_total
            total_display += native_total
            convert_statuses.append("ok")
            continue
        converted, st = convert_amount_with_fill_from_maps(
            native_total,
            ccy,
            disp_ccy,
            effective_as_of,
            fx_maps,
        )
        convert_statuses.append(st)
        display_value_by_currency[ccy] = converted
        if converted is None:
            any_fx_missing = True
        else:
            total_display += converted

    warnings: list[str] = []
    if any_fx_missing:
        warnings.append(CASH_FX_PARTIAL_WARNING)

    fx_status = _combine_cash_fx_status(convert_statuses + per_portfolio_statuses)

    return CashDisplaySummary(
        display_currency=disp_ccy,
        as_of_date=effective_as_of,
        balances=per_portfolio_display,
        totals_by_currency=sorted(currency_totals.items(), key=lambda x: x[0]),
        display_value_by_currency=display_value_by_currency,
        total_display_value=total_display,
        fx_status=fx_status,
        warnings=warnings,
    )


def cash_allocation_rows(summary: CashDisplaySummary) -> list[dict]:
    """Allocation slices for cash — one row per native currency in scope."""
    rows: list[dict] = []
    for ccy, native_total in summary.totals_by_currency:
        if native_total == 0:
            continue
        display_value = summary.display_value_by_currency.get(ccy)
        if display_value is None:
            continue
        rows.append(
            {
                "asset_type": "CASH",
                "asset_symbol": f"Cash {ccy}",
                "primary_asset_class": "CASH",
                "currency": summary.display_currency,
                "native_currency": ccy,
                "native_balance": float(native_total),
                "current_value": float(display_value),
                "holding_status": "ok",
                "is_cash": True,
            }
        )
    return rows


def cash_summary_payload(summary: CashDisplaySummary) -> dict:
    return {
        "display_currency": summary.display_currency,
        "total_display_value": float(summary.total_display_value),
        "balances": [
            {
                "portfolio_id": row.portfolio_id,
                "portfolio_name": row.portfolio_name,
                "currency": row.currency,
                "native_balance": float(row.native_balance),
                "display_value": float(row.display_value)
                if row.display_value is not None
                else None,
            }
            for row in summary.balances
            if row.native_balance != 0 or row.display_value
        ],
    }


def build_cash_value_timeseries(
    scope: ResolvedPortfolioScope,
    display_currency: str,
    *,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Daily end-of-day cash totals for ``scope`` in ``display_currency``.

    Aggregates native balances per currency across portfolios, then converts each
    day using cached FX (7-day fill). Missing FX for a currency on a day excludes
    that currency's amount for that day and marks ``fx_status`` as ``fx_unavailable``.
    """
    if end_date < start_date:
        return []

    entries = _entries_for_scope(scope)
    if not entries:
        return []

    disp_ccy = _norm_display_currency(display_currency)
    by_portfolio_currency: dict[tuple[int, str], list[CashLedgerPoint]] = {}
    for entry in entries:
        key = (entry.portfolio_id, entry.currency)
        by_portfolio_currency.setdefault(key, []).append(ledger_entry_to_point(entry))

    currencies = {entry.currency for entry in entries}
    daily_native: dict[str, dict[date, Decimal]] = {c: {} for c in currencies}

    for (_pid, ccy), points in by_portfolio_currency.items():
        series = cash_balance_timeseries(points, start_date, end_date)
        for day, bal in series.get(ccy, []):
            daily_native[ccy][day] = daily_native[ccy].get(day, Decimal("0")) + bal

    fx_pairs = {(c, disp_ccy) for c in currencies if c != disp_ccy}
    fx_start = start_date - timedelta(days=FX_LOOKBACK_DAYS)
    fx_maps = load_fx_rate_maps(fx_pairs, fx_start, end_date) if fx_pairs else {}

    days: set[date] = set()
    for ccy_map in daily_native.values():
        days.update(ccy_map.keys())
    if not days:
        return []

    result: list[dict] = []
    d = start_date
    while d <= end_date:
        total = Decimal("0")
        day_fx_status = "ok"
        for ccy in sorted(currencies):
            native = daily_native[ccy].get(d, Decimal("0"))
            if native == 0:
                continue
            if ccy == disp_ccy:
                total += native
                continue
            converted, st = convert_amount_with_fill_from_maps(
                native, ccy, disp_ccy, d, fx_maps
            )
            if converted is None:
                day_fx_status = "fx_unavailable"
            else:
                total += converted
                if st == "filled" and day_fx_status == "ok":
                    day_fx_status = "filled"
        result.append(
            {
                "date": d.isoformat(),
                "cash_value": float(total),
                "fx_status": day_fx_status,
            }
        )
        d += timedelta(days=1)

    return result


def merge_cash_into_value_timeseries(
    investment_ts: list[dict],
    *,
    scope: ResolvedPortfolioScope,
    display_currency: str,
    start_date: date,
    end_date: date,
) -> tuple[list[dict], list[str]]:
    """
    Add daily cash display totals to investment ``portfolio_value`` rows.

    When ``investment_ts`` is empty, returns a cash-only series over
    ``[start_date, end_date]``.
    """
    cash_ts = build_cash_value_timeseries(
        scope,
        display_currency,
        start_date=start_date,
        end_date=end_date,
    )
    warnings: list[str] = []
    if cash_ts and any(p.get("fx_status") == "fx_unavailable" for p in cash_ts):
        warnings.append(CASH_FX_VALUE_HISTORY_WARNING)

    if not cash_ts:
        return investment_ts, warnings

    if not investment_ts:
        return [
            {
                "date": p["date"],
                "portfolio_value": p["cash_value"],
                "invested_amount": 0.0,
                "fx_status": p.get("fx_status", "ok"),
            }
            for p in cash_ts
        ], warnings

    cash_by_date = {p["date"]: p for p in cash_ts}
    out: list[dict] = []
    for row in investment_ts:
        merged = dict(row)
        cash_pt = cash_by_date.get(row["date"])
        cash_val = float(cash_pt["cash_value"]) if cash_pt else 0.0
        inv_val = row.get("portfolio_value")
        if inv_val is None:
            # Do not substitute broker cash when investment value is unknown.
            merged["portfolio_value"] = None
        else:
            merged["portfolio_value"] = float(inv_val) + cash_val
        if cash_pt:
            merged["fx_status"] = _combine_cash_fx_status(
                [merged.get("fx_status", "ok"), cash_pt.get("fx_status", "ok")]
            )
        out.append(merged)
    return out, warnings


def cash_value_history_warnings(
    scope: ResolvedPortfolioScope,
    display_currency: str,
    *,
    start_date: date,
    end_date: date,
) -> list[str]:
    cash_ts = build_cash_value_timeseries(
        scope,
        display_currency,
        start_date=start_date,
        end_date=end_date,
    )
    if cash_ts and any(p.get("fx_status") == "fx_unavailable" for p in cash_ts):
        return [CASH_FX_VALUE_HISTORY_WARNING]
    return []


def scope_has_cash_ledger_entries(scope: ResolvedPortfolioScope) -> bool:
    if not scope.portfolio_ids:
        return False
    return CashLedgerEntry.objects.filter(
        portfolio_id__in=scope.portfolio_ids
    ).exists()


def cash_ledger_inception_date(scope: ResolvedPortfolioScope) -> date | None:
    entries = _entries_for_scope(scope)
    if not entries:
        return None
    return min(entry.date for entry in entries)


def list_cash_ledger_entries(
    scope: ResolvedPortfolioScope,
    *,
    currency: str | None = None,
    entry_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> CashLedgerListResult:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise CashValidationError("date_from must not be after date_to")

    if not scope.portfolio_ids:
        return CashLedgerListResult(
            items=[], total=0, page=page, page_size=page_size, pages=1
        )

    qs = CashLedgerEntry.objects.filter(
        portfolio_id__in=scope.portfolio_ids
    ).select_related(
        "portfolio",
        "linked_transaction",
        "linked_transaction__mutual_fund_detail",
        "linked_transaction__mutual_fund_detail__folio",
        "transfer_group",
        "transfer_group__source_portfolio",
        "transfer_group__target_portfolio",
    )
    if currency is not None:
        qs = qs.filter(currency=currency)
    if entry_type is not None:
        qs = qs.filter(entry_type=entry_type)
    if date_from is not None:
        qs = qs.filter(date__gte=date_from)
    if date_to is not None:
        qs = qs.filter(date__lte=date_to)

    qs = qs.order_by("-date", "-id")
    total = qs.count()
    pages = max(1, math.ceil(total / page_size)) if page_size > 0 else 1
    offset = (page - 1) * page_size
    items = list(qs[offset : offset + page_size])

    return CashLedgerListResult(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@db_transaction.atomic
def update_cash_ledger_entry(
    user: AbstractBaseUser,
    entry_id: int,
    *,
    entry_date: date | str,
    currency: str,
    amount,
    source_of_funds: str = "",
    note: str = "",
) -> CashLedgerEntry:
    entry = _ledger_entry_for_user(user, entry_id)
    _require_manual_editable(entry)
    portfolio = entry.portfolio
    old_date = entry.date
    old_currency = entry.currency
    parsed_date = parse_ledger_date(entry_date)
    ccy = validate_cash_currency(currency)
    positive = parse_positive_request_amount(amount)

    if entry.entry_type == CashEntryType.CASH_WITHDRAWAL:
        signed = -positive
        available = _withdrawal_available_on_date(
            portfolio, ccy, parsed_date, exclude_entry_id=entry.id
        )
        if available < positive:
            raise InsufficientCashError(
                "Insufficient cash balance for withdrawal.",
                required=positive,
                available=available,
                shortfall=positive - available,
                currency=ccy,
            )
    else:
        signed = positive

    proposed = CashLedgerPoint(date=parsed_date, currency=ccy, amount=signed)
    from_date = min(old_date, parsed_date)

    if ccy == old_currency:
        validate_non_negative_cash_after_change(
            portfolio,
            ccy,
            exclude_entry_id=entry.id,
            proposed_point=proposed,
            from_date=from_date,
        )
    else:
        validate_non_negative_cash_after_change(
            portfolio,
            old_currency,
            exclude_entry_id=entry.id,
            proposed_point=None,
            from_date=old_date,
        )
        validate_non_negative_cash_after_change(
            portfolio,
            ccy,
            exclude_entry_id=entry.id,
            proposed_point=proposed,
            from_date=parsed_date,
        )

    entry.date = parsed_date
    entry.currency = ccy
    entry.amount = signed
    entry.source_of_funds = (source_of_funds or "").strip()
    entry.note = (note or "").strip()
    entry.full_clean()
    entry.save()
    return _reload_ledger_entry(entry.id)


@db_transaction.atomic
def delete_cash_ledger_entry(user: AbstractBaseUser, entry_id: int) -> None:
    entry = _ledger_entry_for_user(user, entry_id)
    _require_manual_editable(entry)
    portfolio = entry.portfolio
    validate_non_negative_cash_after_change(
        portfolio,
        entry.currency,
        exclude_entry_id=entry.id,
        proposed_point=None,
        from_date=entry.date,
    )
    entry.delete()
