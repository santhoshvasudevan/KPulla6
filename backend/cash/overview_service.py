"""Read-only unified broker + bank cash overview (CASH-UNIFY-1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from cash.services import (
    CASH_FX_PARTIAL_WARNING,
    FX_LOOKBACK_DAYS,
    CashBalanceRow,
    CashBalancesAllResult,
    CashBalancesSingleResult,
    _combine_cash_fx_status,
    _norm_display_currency,
    cash_balances_for_scope,
)
from debt.bank_account_portfolio import (
    PortfolioAssignmentStatus,
    bank_account_portfolio_assignment_status,
)
from debt.bank_ledger_services import compute_bank_account_balance
from debt.models import BankAccount
from fx.lookup import convert_amount_with_fill_from_maps, load_fx_rate_maps
from portfolios import dates as portfolio_dates
from portfolios.scope import ResolvedPortfolioScope

BROKER_CASH_LABEL = "Broker Cash"
BANK_CASH_LABEL = "Bank Cash"
BROKER_AVAILABLE_FOR = "securities / broker transactions"
BANK_AVAILABLE_FOR = "fixed deposits / bank products"

UNASSIGNED_BANK_ACCOUNTS_WARNING = (
    "{count} bank account(s) excluded because portfolio ownership is not assigned."
)
AMBIGUOUS_BANK_ACCOUNTS_WARNING = (
    "{count} bank account(s) excluded because portfolio ownership is ambiguous."
)


@dataclass(frozen=True)
class CashOverviewResult:
    as_of_date: date
    portfolio_scope: str
    portfolio_id: int | None
    display_currency: str | None
    rows: list[dict[str, Any]]
    totals: dict[str, Any]
    warnings: list[str]
    excluded_unassigned_bank_account_count: int
    excluded_ambiguous_bank_account_count: int


def _float_or_none(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _broker_rows_for_scope(
    scope: ResolvedPortfolioScope,
    *,
    as_of_date: date,
) -> list[CashBalanceRow]:
    raw = cash_balances_for_scope(scope, as_of_date=as_of_date)
    if isinstance(raw, CashBalancesSingleResult):
        return [
            CashBalanceRow(
                portfolio_id=raw.portfolio_id,
                portfolio_name=raw.portfolio_name,
                currency=ccy,
                balance=bal,
            )
            for ccy, bal in raw.balances
        ]
    return list(raw.balances)


def _bank_accounts_for_user(user: AbstractBaseUser) -> list[BankAccount]:
    return list(
        BankAccount.objects.filter(user=user, is_active=True)
        .select_related("portfolio")
        .order_by("name", "id")
    )


def _bank_account_in_overview_scope(
    account: BankAccount,
    scope: ResolvedPortfolioScope,
    *,
    include_unassigned: bool,
) -> tuple[bool, str | None]:
    """
    Return (include, exclusion_reason) where exclusion_reason is
    'unassigned' | 'ambiguous' | None.
    """
    status = bank_account_portfolio_assignment_status(account)
    if status == PortfolioAssignmentStatus.ASSIGNED.value:
        if scope.kind == "single":
            return account.portfolio_id == scope.portfolio_ids[0], None
        return True, None

    if status == PortfolioAssignmentStatus.AMBIGUOUS.value:
        if include_unassigned:
            return True, "ambiguous"
        return False, "ambiguous"

    # UNASSIGNED
    if include_unassigned:
        return True, "unassigned"
    return False, "unassigned"


def build_cash_overview(
    user: AbstractBaseUser,
    scope: ResolvedPortfolioScope,
    *,
    as_of_date: date | None = None,
    display_currency: str | None = None,
    include_unassigned: bool = False,
) -> CashOverviewResult:
    effective_as_of = as_of_date or portfolio_dates.current_date()
    disp_ccy = _norm_display_currency(display_currency) if display_currency else None

    warnings: list[str] = []
    excluded_unassigned = 0
    excluded_ambiguous = 0

    broker_rows = _broker_rows_for_scope(scope, as_of_date=effective_as_of)
    bank_accounts = _bank_accounts_for_user(user)

    included_bank: list[tuple[BankAccount, str | None]] = []
    for account in bank_accounts:
        include, reason = _bank_account_in_overview_scope(
            account, scope, include_unassigned=include_unassigned
        )
        if include:
            included_bank.append((account, reason))
        elif reason == "unassigned":
            excluded_unassigned += 1
        elif reason == "ambiguous":
            excluded_ambiguous += 1

    if excluded_unassigned:
        warnings.append(
            UNASSIGNED_BANK_ACCOUNTS_WARNING.format(count=excluded_unassigned)
        )
    if excluded_ambiguous:
        warnings.append(
            AMBIGUOUS_BANK_ACCOUNTS_WARNING.format(count=excluded_ambiguous)
        )

    native_amounts: list[tuple[str, str, Decimal]] = []
    rows: list[dict[str, Any]] = []

    fx_maps = {}
    fx_start = effective_as_of - timedelta(days=FX_LOOKBACK_DAYS)
    if disp_ccy:
        currencies: set[str] = set()
        for row in broker_rows:
            currencies.add(row.currency)
        for account, _ in included_bank:
            currencies.add(account.currency)
        fx_pairs = {(ccy, disp_ccy) for ccy in currencies if ccy != disp_ccy}
        if fx_pairs:
            fx_maps = load_fx_rate_maps(fx_pairs, fx_start, effective_as_of)

    row_fx_statuses: list[str] = []

    def _apply_display(entry: dict[str, Any], amount: Decimal, currency: str) -> None:
        if not disp_ccy:
            return
        entry["display_currency"] = disp_ccy
        if amount == 0 or currency == disp_ccy:
            entry["balance_display"] = float(amount)
            row_fx_statuses.append("ok")
            return
        converted, st = convert_amount_with_fill_from_maps(
            amount, currency, disp_ccy, effective_as_of, fx_maps
        )
        entry["balance_display"] = _float_or_none(converted)
        row_fx_statuses.append(st)

    for row in broker_rows:
        native_amounts.append(("BROKER_CASH", row.currency, row.balance))
        entry: dict[str, Any] = {
            "ledger_type": "BROKER_CASH",
            "portfolio_id": row.portfolio_id,
            "portfolio_name": row.portfolio_name,
            "currency": row.currency,
            "balance": float(row.balance),
            "account_label": BROKER_CASH_LABEL,
            "available_for": BROKER_AVAILABLE_FOR,
            "source": "cash_ledger_entries",
        }
        _apply_display(entry, row.balance, row.currency)
        rows.append(entry)

    for account, inclusion_reason in included_bank:
        balance = compute_bank_account_balance(account, as_of_date=effective_as_of)
        status = bank_account_portfolio_assignment_status(account)
        native_amounts.append(("BANK_CASH", account.currency, balance))
        entry = {
            "ledger_type": "BANK_CASH",
            "bank_account_id": account.id,
            "bank_account_name": account.name,
            "institution_name": account.institution_name,
            "account_number": account.account_number,
            "portfolio_id": account.portfolio_id,
            "portfolio_name": account.portfolio.name if account.portfolio_id else None,
            "portfolio_assignment_status": status,
            "currency": account.currency,
            "balance": float(balance),
            "include_in_portfolio_value": account.include_in_portfolio_value,
            "account_label": BANK_CASH_LABEL,
            "available_for": BANK_AVAILABLE_FOR,
            "source": "cash_movements",
        }
        if inclusion_reason in ("unassigned", "ambiguous"):
            entry["portfolio_assignment_status"] = (
                PortfolioAssignmentStatus.AMBIGUOUS.value
                if inclusion_reason == "ambiguous"
                else PortfolioAssignmentStatus.UNASSIGNED.value
            )
        _apply_display(entry, balance, account.currency)
        rows.append(entry)

    totals_by_currency: dict[str, dict[str, Decimal]] = {}
    for ledger_type, ccy, amount in native_amounts:
        bucket = totals_by_currency.setdefault(
            ccy, {"broker_cash": Decimal("0"), "bank_cash": Decimal("0")}
        )
        if ledger_type == "BROKER_CASH":
            bucket["broker_cash"] += amount
        else:
            bucket["bank_cash"] += amount

    per_currency_totals = []
    for ccy in sorted(totals_by_currency):
        parts = totals_by_currency[ccy]
        total = parts["broker_cash"] + parts["bank_cash"]
        per_currency_totals.append(
            {
                "currency": ccy,
                "broker_cash": float(parts["broker_cash"]),
                "bank_cash": float(parts["bank_cash"]),
                "total_cash": float(total),
            }
        )

    totals: dict[str, Any] = {
        "as_of_date": effective_as_of.isoformat(),
        "by_currency": per_currency_totals,
    }

    fx_status = "ok"
    if disp_ccy:
        total_broker_display = Decimal("0")
        total_bank_display = Decimal("0")
        broker_display_complete = True
        bank_display_complete = True

        for ledger_type, ccy, amount in native_amounts:
            if amount == 0 or ccy == disp_ccy:
                converted = amount
                st = "ok"
            else:
                converted, st = convert_amount_with_fill_from_maps(
                    amount, ccy, disp_ccy, effective_as_of, fx_maps
                )
            if st not in ("ok", "filled") or converted is None:
                if ledger_type == "BROKER_CASH":
                    broker_display_complete = False
                else:
                    bank_display_complete = False
                continue
            if ledger_type == "BROKER_CASH":
                total_broker_display += converted
            else:
                total_bank_display += converted

        fx_status = _combine_cash_fx_status(row_fx_statuses) if row_fx_statuses else "ok"
        if fx_status != "ok":
            warnings.append(CASH_FX_PARTIAL_WARNING)

        totals["display_currency"] = disp_ccy
        totals["fx_status"] = fx_status
        totals["broker_cash_display"] = (
            float(total_broker_display) if broker_display_complete else None
        )
        totals["bank_cash_display"] = (
            float(total_bank_display) if bank_display_complete else None
        )
        if broker_display_complete and bank_display_complete:
            totals["total_cash_display"] = float(
                total_broker_display + total_bank_display
            )
        else:
            totals["total_cash_display"] = None
    else:
        aggregate_broker = sum(
            (parts["broker_cash"] for parts in totals_by_currency.values()),
            Decimal("0"),
        )
        aggregate_bank = sum(
            (parts["bank_cash"] for parts in totals_by_currency.values()),
            Decimal("0"),
        )
        totals["broker_cash"] = float(aggregate_broker)
        totals["bank_cash"] = float(aggregate_bank)
        totals["total_cash"] = float(aggregate_broker + aggregate_bank)

    scope_label = "all" if scope.kind == "all_active" else "single"
    portfolio_id = scope.portfolio_ids[0] if scope.kind == "single" else None

    return CashOverviewResult(
        as_of_date=effective_as_of,
        portfolio_scope=scope_label,
        portfolio_id=portfolio_id,
        display_currency=disp_ccy,
        rows=rows,
        totals=totals,
        warnings=warnings,
        excluded_unassigned_bank_account_count=excluded_unassigned,
        excluded_ambiguous_bank_account_count=excluded_ambiguous,
    )


def cash_overview_to_response_dict(result: CashOverviewResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "portfolio_scope": result.portfolio_scope,
        "as_of_date": result.as_of_date.isoformat(),
        "rows": result.rows,
        "totals": result.totals,
        "warnings": result.warnings,
        "excluded_unassigned_bank_account_count": result.excluded_unassigned_bank_account_count,
        "excluded_ambiguous_bank_account_count": result.excluded_ambiguous_bank_account_count,
    }
    if result.portfolio_id is not None:
        payload["portfolio_id"] = result.portfolio_id
    if result.display_currency:
        payload["display_currency"] = result.display_currency
    return payload
