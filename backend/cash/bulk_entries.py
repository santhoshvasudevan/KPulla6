"""Bulk manual cash deposit/withdrawal schedule preview and apply (Cash-7D)."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction as db_transaction

from cash.models import CashEntryType, CashLedgerEntry
from cash.services import (
    CashValidationError,
    list_ledger_points_for_portfolio,
    parse_positive_request_amount,
    validate_cash_currency,
)
from finance.cash import CashLedgerPoint, cash_balance_timeseries
from portfolios.models import Portfolio

_SUPPORTED_FREQUENCIES = frozenset({"once", "monthly"})
_BULK_ENTRY_TYPES = frozenset(
    {CashEntryType.CASH_DEPOSIT, CashEntryType.CASH_WITHDRAWAL}
)
_LEDGER_AMOUNT_QUANT = Decimal("0.0001")
_MAX_SCHEDULE_ENTRIES = 500


class BulkEntriesValidationError(CashValidationError):
    pass


class BulkEntriesBlockedError(BulkEntriesValidationError):
    """Apply blocked — e.g. withdrawal schedule would drive balance negative."""

    def __init__(self, message: str, *, warnings: list[str] | None = None) -> None:
        super().__init__(message)
        self.warnings = warnings or []


@dataclass(frozen=True)
class BulkEntryRow:
    date: date
    currency: str
    entry_type: str
    amount: Decimal
    source_of_funds: str
    note: str


@dataclass
class BulkEntriesPreviewResult:
    portfolio: Portfolio
    entry_count: int
    entries: list[BulkEntryRow]
    total_by_currency: list[tuple[str, Decimal]]
    warnings: list[str] = field(default_factory=list)
    duplicate_count: int = 0


@dataclass
class BulkEntriesApplyResult:
    portfolio: Portfolio
    created_count: int
    skipped_existing_count: int
    created_entries: list[CashLedgerEntry]
    total_by_currency: list[tuple[str, Decimal]]


def _ledger_amount(amount: Decimal) -> Decimal:
    return amount.quantize(_LEDGER_AMOUNT_QUANT)


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _normalize_frequency(frequency: str) -> str:
    code = (frequency or "").strip().lower()
    if code not in _SUPPORTED_FREQUENCIES:
        raise BulkEntriesValidationError(
            f"Unsupported frequency: {frequency!r}. Use once or monthly."
        )
    return code


def _normalize_entry_type(entry_type: str) -> str:
    code = (entry_type or "").strip().upper()
    if code not in _BULK_ENTRY_TYPES:
        raise BulkEntriesValidationError(
            "entry_type must be CASH_DEPOSIT or CASH_WITHDRAWAL."
        )
    return code


def generate_schedule_dates(
    *,
    start_date: date,
    end_date: date,
    frequency: str,
) -> list[date]:
    frequency = _normalize_frequency(frequency)
    if frequency == "once":
        return [start_date]
    dates: list[date] = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current = _add_months(current, 1)
    return dates


def _signed_amount(entry_type: str, positive_amount: Decimal) -> Decimal:
    amt = _ledger_amount(positive_amount)
    if entry_type == CashEntryType.CASH_WITHDRAWAL:
        return -amt
    return amt


def _find_existing_manual_entry(
    portfolio_id: int,
    *,
    entry_date: date,
    currency: str,
    entry_type: str,
    signed_amount: Decimal,
    source_of_funds: str,
    note: str,
) -> CashLedgerEntry | None:
    return (
        CashLedgerEntry.objects.filter(
            portfolio_id=portfolio_id,
            date=entry_date,
            currency=currency,
            entry_type=entry_type,
            amount=signed_amount,
            source_of_funds=source_of_funds,
            note=note,
            linked_transaction__isnull=True,
            transfer_group__isnull=True,
        )
        .order_by("id")
        .first()
    )


def _withdrawal_schedule_warning(
    portfolio: Portfolio,
    currency: str,
    rows: list[BulkEntryRow],
) -> str | None:
    withdrawal_rows = [
        r for r in rows if r.entry_type == CashEntryType.CASH_WITHDRAWAL
    ]
    if not withdrawal_rows:
        return None

    existing = list_ledger_points_for_portfolio(portfolio, currency=currency)
    proposed = [
        CashLedgerPoint(
            date=r.date,
            currency=r.currency,
            amount=-_ledger_amount(r.amount),
        )
        for r in withdrawal_rows
    ]
    all_points = existing + proposed
    if not all_points:
        return None

    start = min(p.date for p in all_points)
    end = max(p.date for p in all_points)
    series = cash_balance_timeseries(all_points, start, end)
    for day, balance in series.get(currency, []):
        if balance < 0:
            return (
                f"Withdrawal schedule would make {currency} cash balance negative "
                f"on {day.isoformat()}."
            )
    return None


def preview_bulk_cash_entries(
    portfolio: Portfolio,
    *,
    entry_type: str,
    currency: str,
    amount,
    start_date: date,
    end_date: date | None = None,
    frequency: str = "once",
    source_of_funds: str = "",
    note: str = "",
) -> BulkEntriesPreviewResult:
    entry_type = _normalize_entry_type(entry_type)
    frequency = _normalize_frequency(frequency)
    ccy = validate_cash_currency(currency)
    positive_amount = _ledger_amount(parse_positive_request_amount(amount))
    source = (source_of_funds or "").strip()
    entry_note = (note or "").strip()

    if frequency == "monthly":
        if end_date is None:
            raise BulkEntriesValidationError(
                "end_date is required for monthly frequency."
            )
        effective_end = end_date
    else:
        effective_end = end_date or start_date

    if start_date > effective_end:
        raise BulkEntriesValidationError("start_date must be on or before end_date")

    schedule_dates = generate_schedule_dates(
        start_date=start_date,
        end_date=effective_end,
        frequency=frequency,
    )
    if len(schedule_dates) > _MAX_SCHEDULE_ENTRIES:
        raise BulkEntriesValidationError(
            f"Schedule exceeds maximum of {_MAX_SCHEDULE_ENTRIES} entries."
        )

    rows: list[BulkEntryRow] = [
        BulkEntryRow(
            date=d,
            currency=ccy,
            entry_type=entry_type,
            amount=positive_amount,
            source_of_funds=source,
            note=entry_note,
        )
        for d in schedule_dates
    ]

    warnings: list[str] = []
    duplicate_count = 0
    signed = _signed_amount(entry_type, positive_amount)
    for row in rows:
        if _find_existing_manual_entry(
            portfolio.id,
            entry_date=row.date,
            currency=row.currency,
            entry_type=row.entry_type,
            signed_amount=signed,
            source_of_funds=row.source_of_funds,
            note=row.note,
        ):
            duplicate_count += 1

    if duplicate_count:
        warnings.append(
            f"{duplicate_count} scheduled entr{'y' if duplicate_count == 1 else 'ies'} "
            "match existing manual ledger rows and will be skipped on apply."
        )

    withdrawal_warning = _withdrawal_schedule_warning(portfolio, ccy, rows)
    if withdrawal_warning:
        warnings.append(withdrawal_warning)

    totals: dict[str, Decimal] = {}
    for row in rows:
        totals[row.currency] = totals.get(row.currency, Decimal("0")) + row.amount

    return BulkEntriesPreviewResult(
        portfolio=portfolio,
        entry_count=len(rows),
        entries=rows,
        total_by_currency=sorted(totals.items()),
        warnings=warnings,
        duplicate_count=duplicate_count,
    )


def _create_manual_entry(
    portfolio: Portfolio,
    row: BulkEntryRow,
) -> CashLedgerEntry:
    signed = _signed_amount(row.entry_type, row.amount)
    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=row.date,
        currency=row.currency,
        entry_type=row.entry_type,
        amount=signed,
        source_of_funds=row.source_of_funds,
        note=row.note,
        linked_transaction=None,
        transfer_group=None,
    )
    entry.full_clean()
    entry.save()
    return entry


@db_transaction.atomic
def apply_bulk_cash_entries(
    portfolio: Portfolio,
    *,
    entry_type: str,
    currency: str,
    amount,
    start_date: date,
    end_date: date | None = None,
    frequency: str = "once",
    source_of_funds: str = "",
    note: str = "",
) -> BulkEntriesApplyResult:
    preview = preview_bulk_cash_entries(
        portfolio,
        entry_type=entry_type,
        currency=currency,
        amount=amount,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        source_of_funds=source_of_funds,
        note=note,
    )

    ccy = validate_cash_currency(currency)
    withdrawal_warning = _withdrawal_schedule_warning(portfolio, ccy, preview.entries)
    if withdrawal_warning:
        raise BulkEntriesBlockedError(
            withdrawal_warning,
            warnings=preview.warnings,
        )

    created: list[CashLedgerEntry] = []
    skipped = 0
    totals: dict[str, Decimal] = {}

    for row in preview.entries:
        signed = _signed_amount(row.entry_type, row.amount)
        existing = _find_existing_manual_entry(
            portfolio.id,
            entry_date=row.date,
            currency=row.currency,
            entry_type=row.entry_type,
            signed_amount=signed,
            source_of_funds=row.source_of_funds,
            note=row.note,
        )
        if existing is not None:
            skipped += 1
            continue
        entry = _create_manual_entry(portfolio, row)
        created.append(entry)
        totals[row.currency] = totals.get(row.currency, Decimal("0")) + row.amount

    portfolio.refresh_from_db(fields=["name"])
    return BulkEntriesApplyResult(
        portfolio=portfolio,
        created_count=len(created),
        skipped_existing_count=skipped,
        created_entries=created,
        total_by_currency=sorted(totals.items()),
    )


def bulk_entries_preview_to_response_dict(
    result: BulkEntriesPreviewResult,
) -> dict[str, Any]:
    return {
        "portfolio_id": result.portfolio.id,
        "portfolio_name": result.portfolio.name,
        "entry_count": result.entry_count,
        "entries": [
            {
                "date": row.date.isoformat(),
                "currency": row.currency,
                "entry_type": row.entry_type,
                "amount": float(row.amount),
                "source_of_funds": row.source_of_funds or None,
                "note": row.note or None,
            }
            for row in result.entries
        ],
        "total_by_currency": [
            {"currency": ccy, "amount": float(amt)}
            for ccy, amt in result.total_by_currency
        ],
        "warnings": result.warnings,
        "duplicate_count": result.duplicate_count,
    }


def bulk_entries_apply_to_response_dict(result: BulkEntriesApplyResult) -> dict[str, Any]:
    p = result.portfolio
    return {
        "portfolio_id": p.id,
        "portfolio_name": p.name,
        "created_count": result.created_count,
        "skipped_existing_count": result.skipped_existing_count,
        "created_entries": [
            {
                "id": e.id,
                "date": e.date.isoformat(),
                "currency": e.currency,
                "entry_type": e.entry_type,
                "amount": float(abs(e.amount)),
                "source_of_funds": e.source_of_funds or None,
                "note": e.note or None,
            }
            for e in result.created_entries
        ],
        "total_by_currency": [
            {"currency": ccy, "amount": float(amt)}
            for ccy, amt in result.total_by_currency
        ],
    }
