"""Legacy cash backfill apply (Cash-7B — confirmed, atomic CASH_DEPOSIT creation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction as db_transaction

from cash.backfill_preview import (
    BackfillPreviewValidationError,
    BackfillProposedDeposit,
    _BACKFILL_SOURCE,
    simulate_cash_backfill_preview,
)
from cash.models import CashEntryType, CashLedgerEntry
from portfolios.models import Portfolio

_BLOCKING_WARNING_PREFIX = "BLOCKING:"
_LEDGER_AMOUNT_QUANT = Decimal("0.0001")


class BackfillApplyValidationError(Exception):
    pass


class BackfillApplyBlockedError(BackfillApplyValidationError):
    """Preview has row_errors or blocking warnings; apply must not write."""

    def __init__(self, *, row_errors: list, blocking_warnings: list) -> None:
        parts: list[str] = []
        if row_errors:
            parts.append("Backfill preview has row errors.")
        if blocking_warnings:
            parts.extend(blocking_warnings)
        super().__init__(" ".join(parts) if parts else "Backfill apply blocked.")
        self.row_errors = row_errors
        self.blocking_warnings = blocking_warnings


@dataclass
class BackfillApplySummary:
    total_created_by_currency: list[tuple[str, Decimal]] = field(default_factory=list)


@dataclass
class BackfillApplyResult:
    portfolio: Portfolio
    created_count: int
    skipped_existing_count: int
    created_deposits: list[CashLedgerEntry]
    summary: BackfillApplySummary


def _ledger_amount(amount: Decimal) -> Decimal:
    return amount.quantize(_LEDGER_AMOUNT_QUANT)


def _format_backfill_note(note: str) -> str:
    text = (note or "").strip()
    if not text:
        return "Backfill: deposit"
    if text.lower().startswith("backfill:"):
        return text
    return f"Backfill: {text}"


def _blocking_warnings(warnings: list[str]) -> list[str]:
    return [
        w
        for w in warnings
        if w.strip().upper().startswith(_BLOCKING_WARNING_PREFIX)
    ]


def _find_existing_backfill_deposit(
    portfolio_id: int,
    *,
    entry_date: date,
    currency: str,
    amount: Decimal,
    source_of_funds: str,
    note: str,
) -> CashLedgerEntry | None:
    return (
        CashLedgerEntry.objects.filter(
            portfolio_id=portfolio_id,
            date=entry_date,
            currency=currency,
            entry_type=CashEntryType.CASH_DEPOSIT,
            amount=amount,
            source_of_funds=source_of_funds,
            note=note,
            linked_transaction__isnull=True,
            transfer_group__isnull=True,
        )
        .order_by("id")
        .first()
    )


def _create_backfill_deposit(
    portfolio: Portfolio,
    proposed: BackfillProposedDeposit,
    *,
    note: str,
    amount: Decimal,
) -> CashLedgerEntry:
    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=proposed.date,
        currency=proposed.currency,
        entry_type=CashEntryType.CASH_DEPOSIT,
        amount=amount,
        source_of_funds=proposed.source_of_funds or _BACKFILL_SOURCE,
        note=note,
        linked_transaction=None,
        transfer_group=None,
    )
    entry.full_clean()
    entry.save()
    return entry


@db_transaction.atomic
def apply_cash_backfill(
    portfolio: Portfolio,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    mode: str = "shortfall",
    today: date | None = None,
) -> BackfillApplyResult:
    """
    Recompute preview server-side, then create proposed CASH_DEPOSIT rows atomically.

    Does not enable cash_aware_enabled. Skips identical existing backfill deposits.
    """
    try:
        preview = simulate_cash_backfill_preview(
            portfolio,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            today=today,
        )
    except BackfillPreviewValidationError as exc:
        raise BackfillApplyValidationError(str(exc)) from exc

    row_errors = list(preview.row_errors)
    blocking = _blocking_warnings(preview.warnings)
    if row_errors or blocking:
        raise BackfillApplyBlockedError(
            row_errors=row_errors, blocking_warnings=blocking
        )

    created: list[CashLedgerEntry] = []
    skipped = 0
    totals: dict[str, Decimal] = {}

    for proposed in preview.proposed_deposits:
        note = _format_backfill_note(proposed.note)
        source = proposed.source_of_funds or _BACKFILL_SOURCE
        amount = _ledger_amount(proposed.amount)
        existing = _find_existing_backfill_deposit(
            portfolio.id,
            entry_date=proposed.date,
            currency=proposed.currency,
            amount=amount,
            source_of_funds=source,
            note=note,
        )
        if existing is not None:
            skipped += 1
            continue
        entry = _create_backfill_deposit(
            portfolio, proposed, note=note, amount=amount
        )
        created.append(entry)
        totals[proposed.currency] = totals.get(proposed.currency, Decimal("0")) + amount

    portfolio.refresh_from_db(fields=["cash_aware_enabled", "name"])
    return BackfillApplyResult(
        portfolio=portfolio,
        created_count=len(created),
        skipped_existing_count=skipped,
        created_deposits=created,
        summary=BackfillApplySummary(
            total_created_by_currency=sorted(totals.items()),
        ),
    )


def backfill_apply_to_response_dict(result: BackfillApplyResult) -> dict[str, Any]:
    p = result.portfolio
    return {
        "portfolio_id": p.id,
        "portfolio_name": p.name,
        "cash_aware_enabled": p.cash_aware_enabled,
        "created_count": result.created_count,
        "skipped_existing_count": result.skipped_existing_count,
        "created_deposits": [
            {
                "id": e.id,
                "date": e.date.isoformat(),
                "currency": e.currency,
                "amount": float(e.amount),
                "entry_type": e.entry_type,
                "source_of_funds": e.source_of_funds or None,
                "note": e.note or None,
            }
            for e in result.created_deposits
        ],
        "summary": {
            "total_created_by_currency": [
                {"currency": ccy, "amount": float(amt)}
                for ccy, amt in result.summary.total_created_by_currency
            ],
        },
        "cash_aware_enablement": {
            "enabled": False,
            "message": (
                "Backfill deposits were created. Enable cash-aware mode separately "
                "after review."
            ),
        },
    }
