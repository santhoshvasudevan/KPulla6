"""Read-only cash unification diagnostics (CASH-UNIFY-4A)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from cash.models import CashEntryType, CashLedgerEntry
from cash.services import cash_balances_for_scope
from portfolios import dates as portfolio_dates
from debt.bank_account_portfolio import bank_account_portfolio_assignment_status
from debt.bank_ledger_services import compute_bank_account_balance
from debt.models import BankAccount, CashMovement
from portfolios.models import Portfolio
from portfolios.scope import resolve_portfolio_scope


MANUAL_BROKER_ENTRY_TYPES = frozenset(
    {CashEntryType.CASH_DEPOSIT, CashEntryType.CASH_WITHDRAWAL}
)


@dataclass(frozen=True)
class CashDiagnosticsResult:
    as_of_date: date
    portfolio_id: int | None
    broker_cash_by_portfolio: list[dict[str, Any]]
    bank_cash_by_portfolio: list[dict[str, Any]]
    unlinked_bank_accounts: list[dict[str, Any]]
    possible_duplicate_entries: list[dict[str, Any]]


def _abs_amount(value: Decimal) -> Decimal:
    return value.copy_abs()


def _broker_cash_by_portfolio(user: AbstractBaseUser) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    portfolios = Portfolio.objects.filter(user=user, is_active=True).order_by("name", "id")
    for portfolio in portfolios:
        scope = resolve_portfolio_scope(user, portfolio_id=portfolio.id)
        raw = cash_balances_for_scope(scope)
        balances = raw.balances if hasattr(raw, "balances") else []
        for currency, balance in balances:
            if balance == 0:
                continue
            rows.append(
                {
                    "portfolio_id": portfolio.id,
                    "portfolio_name": portfolio.name,
                    "currency": currency,
                    "balance": float(balance),
                }
            )
    return rows


def _bank_cash_by_portfolio(user: AbstractBaseUser) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    linked_rows: list[dict[str, Any]] = []
    unlinked_rows: list[dict[str, Any]] = []
    accounts = BankAccount.objects.filter(user=user, is_active=True).select_related("portfolio")
    for account in accounts:
        balance = compute_bank_account_balance(account)
        if balance == 0:
            continue
        status = bank_account_portfolio_assignment_status(account)
        row = {
            "bank_account_id": account.id,
            "bank_account_name": account.name,
            "institution_name": account.institution_name,
            "currency": account.currency,
            "balance": float(balance),
            "portfolio_assignment_status": status,
            "portfolio_id": account.portfolio_id,
            "portfolio_name": account.portfolio.name if account.portfolio_id else None,
        }
        if account.portfolio_id and status == "ASSIGNED":
            linked_rows.append(row)
        else:
            unlinked_rows.append(row)
    return linked_rows, unlinked_rows


def _find_possible_duplicate_entries(user: AbstractBaseUser) -> list[dict[str, Any]]:
    broker_entries = (
        CashLedgerEntry.objects.filter(
            portfolio__user=user,
            entry_type__in=MANUAL_BROKER_ENTRY_TYPES,
            is_reversal=False,
            linked_transaction_id__isnull=True,
            transfer_group_id__isnull=True,
        )
        .select_related("portfolio")
        .order_by("date", "id")
    )
    bank_movements = (
        CashMovement.objects.filter(user=user)
        .select_related("bank_account", "bank_account__portfolio")
        .order_by("movement_date", "id")
    )

    bank_index: dict[tuple[date, str, Decimal], list[CashMovement]] = defaultdict(list)
    for movement in bank_movements:
        key = (movement.movement_date, movement.currency, _abs_amount(movement.amount))
        bank_index[key].append(movement)

    duplicates: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for entry in broker_entries:
        key = (entry.date, entry.currency, _abs_amount(entry.amount))
        matches = bank_index.get(key, [])
        if not matches:
            continue
        for movement in matches:
            pair_key = (entry.id, movement.id)
            if pair_key in seen:
                continue
            seen.add(pair_key)
            duplicates.append(
                {
                    "date": entry.date.isoformat(),
                    "currency": entry.currency,
                    "amount": float(_abs_amount(entry.amount)),
                    "broker_entry_id": entry.id,
                    "broker_entry_type": entry.entry_type,
                    "broker_portfolio_id": entry.portfolio_id,
                    "broker_portfolio_name": entry.portfolio.name,
                    "bank_movement_id": movement.id,
                    "bank_movement_type": movement.movement_type,
                    "bank_account_id": movement.bank_account_id,
                    "bank_account_name": movement.bank_account.name,
                    "bank_portfolio_id": movement.bank_account.portfolio_id,
                    "note": (
                        "Same date and absolute amount in broker ledger and bank ledger — "
                        "possible mistaken broker entry or duplicate recording."
                    ),
                }
            )
    return duplicates


def build_cash_diagnostics(
    user: AbstractBaseUser,
    *,
    portfolio_id: int | None = None,
    as_of_date: date | None = None,
) -> CashDiagnosticsResult:
    effective_as_of = as_of_date or portfolio_dates.current_date()
    broker_rows = _broker_cash_by_portfolio(user)
    bank_linked, unlinked = _bank_cash_by_portfolio(user)
    if portfolio_id is not None:
        broker_rows = [r for r in broker_rows if r["portfolio_id"] == portfolio_id]
        bank_linked = [r for r in bank_linked if r["portfolio_id"] == portfolio_id]

    return CashDiagnosticsResult(
        as_of_date=effective_as_of,
        portfolio_id=portfolio_id,
        broker_cash_by_portfolio=broker_rows,
        bank_cash_by_portfolio=bank_linked,
        unlinked_bank_accounts=unlinked,
        possible_duplicate_entries=_find_possible_duplicate_entries(user),
    )


def cash_diagnostics_to_dict(result: CashDiagnosticsResult) -> dict[str, Any]:
    return {
        "as_of_date": result.as_of_date.isoformat(),
        "portfolio_id": result.portfolio_id,
        "broker_cash_by_portfolio": result.broker_cash_by_portfolio,
        "bank_cash_by_portfolio": result.bank_cash_by_portfolio,
        "unlinked_bank_accounts": result.unlinked_bank_accounts,
        "possible_duplicate_entries": result.possible_duplicate_entries,
        "duplicate_count": len(result.possible_duplicate_entries),
    }
