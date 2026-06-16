"""Bank cash movement classification for portfolio return metrics (FD-ACC-8C)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Callable, Optional

from debt.bank_ledger_services import bank_account_has_ledger
from debt.models import (
    BankAccount,
    CashMovement,
    CashMovementDirection,
    CashMovementType,
)
from debt.portfolio_value import bank_account_includable_in_scope
from finance.bank_cash import signed_movement_amount
from fx.lookup import convert_amount_with_fill_from_maps, load_fx_rate_maps
from portfolios.scope import ResolvedPortfolioScope
from portfolios.summary_service import norm_display_currency

FX_LOOKBACK_DAYS = 7


class BankCashFlowKind(str, Enum):
    EXTERNAL_CONTRIBUTION = "external_contribution"
    EXTERNAL_WITHDRAWAL = "external_withdrawal"
    INTERNAL = "internal"
    INCOME_RETURN = "income_return"
    IGNORED = "ignored"


_INTERNAL_MOVEMENT_TYPES = frozenset(
    {
        CashMovementType.FD_OPENING,
        CashMovementType.FD_MATURITY_PRINCIPAL,
        CashMovementType.FD_CLOSURE_PRINCIPAL,
        CashMovementType.TRANSFER_IN,
        CashMovementType.TRANSFER_OUT,
    }
)

_INCOME_RETURN_MOVEMENT_TYPES = frozenset(
    {
        CashMovementType.FD_INTEREST,
        CashMovementType.FD_MATURITY_INTEREST,
        CashMovementType.FD_CLOSURE_INTEREST,
    }
)

_EXTERNAL_CONTRIBUTION_TYPES = frozenset(
    {
        CashMovementType.MANUAL_DEPOSIT,
        CashMovementType.OPENING_BALANCE,
    }
)

_EXTERNAL_WITHDRAWAL_TYPES = frozenset(
    {
        CashMovementType.MANUAL_WITHDRAWAL,
    }
)


def classify_bank_cash_movement(
    movement: CashMovement,
    *,
    bank_included: bool,
) -> BankCashFlowKind:
    """
    Classify a bank ``CashMovement`` for portfolio return metrics.

    Only movements on opt-in included accounts with a ledger participate in
    external-flow maps. FD system movements and interest credits are internal
    or income; manual deposits/withdrawals and opening-balance seeds are external.
    """
    if not bank_included or movement.is_reversal:
        return BankCashFlowKind.IGNORED

    movement_type = movement.movement_type
    if movement_type in _INTERNAL_MOVEMENT_TYPES:
        return BankCashFlowKind.INTERNAL
    if movement_type in _INCOME_RETURN_MOVEMENT_TYPES:
        return BankCashFlowKind.INCOME_RETURN
    if movement_type in _EXTERNAL_CONTRIBUTION_TYPES:
        return BankCashFlowKind.EXTERNAL_CONTRIBUTION
    if movement_type in _EXTERNAL_WITHDRAWAL_TYPES:
        return BankCashFlowKind.EXTERNAL_WITHDRAWAL
    if movement_type == CashMovementType.ADJUSTMENT:
        if movement.direction == CashMovementDirection.CREDIT:
            return BankCashFlowKind.EXTERNAL_CONTRIBUTION
        if movement.direction == CashMovementDirection.DEBIT:
            return BankCashFlowKind.EXTERNAL_WITHDRAWAL
    return BankCashFlowKind.IGNORED


def _eligible_accounts(user, scope: ResolvedPortfolioScope) -> list[BankAccount]:
    accounts = list(
        BankAccount.objects.filter(
            user=user,
            is_active=True,
            include_in_portfolio_value=True,
        ).order_by("name", "id")
    )
    return [
        account
        for account in accounts
        if bank_account_includable_in_scope(account, scope)
        and bank_account_has_ledger(account)
    ]


def twror_flow_amount_from_bank_movement(movement: CashMovement) -> Decimal:
    """TWROR external flow in native currency (contribution +, withdrawal -)."""
    kind = classify_bank_cash_movement(movement, bank_included=True)
    signed = signed_movement_amount(movement.amount, movement.direction)
    if kind == BankCashFlowKind.EXTERNAL_CONTRIBUTION:
        return abs(signed)
    if kind == BankCashFlowKind.EXTERNAL_WITHDRAWAL:
        return -abs(signed)
    return Decimal("0")


def xirr_flow_amount_from_bank_movement(movement: CashMovement) -> Decimal:
    """Investor-perspective XIRR flow (contribution -, withdrawal +)."""
    twror_amt = twror_flow_amount_from_bank_movement(movement)
    if twror_amt == 0:
        return Decimal("0")
    return -twror_amt


def build_bank_cash_external_flows(
    user,
    scope: ResolvedPortfolioScope,
    *,
    calculation_currency: str,
    amount_mapper: Callable[[CashMovement], Decimal],
) -> tuple[dict[date, Decimal], Optional[date]]:
    """External bank-cash flows by date for included accounts in scope."""
    if user is None:
        return {}, None

    accounts = _eligible_accounts(user, scope)
    if not accounts:
        return {}, None

    account_ids = [account.id for account in accounts]
    movements = list(
        CashMovement.objects.filter(
            bank_account_id__in=account_ids,
            is_reversal=False,
        ).order_by("movement_date", "id")
    )
    external_rows = [
        row
        for row in movements
        if classify_bank_cash_movement(row, bank_included=True)
        in {
            BankCashFlowKind.EXTERNAL_CONTRIBUTION,
            BankCashFlowKind.EXTERNAL_WITHDRAWAL,
        }
    ]
    if not external_rows:
        return {}, None

    calc_ccy = norm_display_currency(calculation_currency)
    flow_dates = [row.movement_date for row in external_rows]
    fx_pairs: set[tuple[str, str]] = set()
    for row in external_rows:
        ccy = (row.currency or calc_ccy).strip().upper()
        if ccy != calc_ccy:
            fx_pairs.add((ccy, calc_ccy))

    fx_start = min(flow_dates) - timedelta(days=FX_LOOKBACK_DAYS)
    fx_end = max(flow_dates)
    fx_maps = load_fx_rate_maps(fx_pairs, fx_start, fx_end) if fx_pairs else {}

    flows_by_date: dict[date, Decimal] = {}
    flows_unknown_from: Optional[date] = None
    for row in external_rows:
        native = amount_mapper(row)
        if native == 0:
            continue
        ccy = (row.currency or calc_ccy).strip().upper()
        if ccy == calc_ccy:
            converted = native
        else:
            converted, _ = convert_amount_with_fill_from_maps(
                native,
                ccy,
                calc_ccy,
                row.movement_date,
                fx_maps,
            )
            if converted is None:
                flows_unknown_from = (
                    min(flows_unknown_from, row.movement_date)
                    if flows_unknown_from
                    else row.movement_date
                )
                continue
            native = converted
        flows_by_date[row.movement_date] = (
            flows_by_date.get(row.movement_date, Decimal("0")) + native
        )
    return flows_by_date, flows_unknown_from


def build_bank_cash_twror_external_flows(
    user,
    scope: ResolvedPortfolioScope,
    *,
    calculation_currency: str,
) -> tuple[dict[date, Decimal], Optional[date]]:
    return build_bank_cash_external_flows(
        user,
        scope,
        calculation_currency=calculation_currency,
        amount_mapper=twror_flow_amount_from_bank_movement,
    )


def build_bank_cash_xirr_external_flows(
    user,
    scope: ResolvedPortfolioScope,
    *,
    calculation_currency: str,
) -> tuple[dict[date, Decimal], bool]:
    flows, unknown = build_bank_cash_external_flows(
        user,
        scope,
        calculation_currency=calculation_currency,
        amount_mapper=xirr_flow_amount_from_bank_movement,
    )
    return flows, unknown is not None
