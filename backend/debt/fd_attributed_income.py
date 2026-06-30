"""Portfolio-attributed FD payout income for performance metrics (FD-PERF-2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.contrib.auth.models import AbstractBaseUser

from debt.bank_ledger_services import bank_account_has_ledger
from debt.models import BankAccount, FixedDepositInterestPayment
from debt.portfolio_value import bank_account_includable_in_scope
from fx.lookup import convert_amount_with_fill_from_maps, load_fx_rate_maps
from portfolios.scope import ResolvedPortfolioScope
from portfolios.summary_service import norm_display_currency

FX_LOOKBACK_DAYS = 7
FD_ATTRIBUTED_INCOME_FX_WARNING = (
    "FX rates are missing for some portfolio-attributed FD interest income points."
)


@dataclass(frozen=True)
class FdAttributedIncomeEvent:
    portfolio_id: int
    fd_id: int
    payment_id: int
    payment_date: date
    gross_interest: Decimal
    tax_withheld: Decimal
    net_interest: Decimal
    currency: str
    bank_account_id: int
    bank_included_in_portfolio_scope: bool
    should_count_as_attributed_income: bool


def bank_represents_interest_in_performance_scope(
    bank_account: BankAccount,
    scope: ResolvedPortfolioScope,
) -> bool:
    """True when net interest is already reflected via included bank cash in scope."""
    if not bank_account.include_in_portfolio_value:
        return False
    if not bank_account_has_ledger(bank_account):
        return False
    return bank_account_includable_in_scope(bank_account, scope)


def _payment_in_scope(payment: FixedDepositInterestPayment, scope: ResolvedPortfolioScope) -> bool:
    return payment.fixed_deposit.portfolio_id in scope.portfolio_ids


def list_fd_attributed_income_events(
    user: AbstractBaseUser,
    scope: ResolvedPortfolioScope,
) -> list[FdAttributedIncomeEvent]:
    payments = (
        FixedDepositInterestPayment.objects.filter(
            user=user,
            is_reversed=False,
            fixed_deposit__portfolio_id__in=scope.portfolio_ids,
        )
        .select_related("fixed_deposit", "bank_account")
        .order_by("payment_date", "id")
    )
    events: list[FdAttributedIncomeEvent] = []
    for payment in payments:
        if not _payment_in_scope(payment, scope):
            continue
        bank = payment.bank_account
        bank_included = bank_represents_interest_in_performance_scope(bank, scope)
        events.append(
            FdAttributedIncomeEvent(
                portfolio_id=payment.fixed_deposit.portfolio_id,
                fd_id=payment.fixed_deposit_id,
                payment_id=payment.id,
                payment_date=payment.payment_date,
                gross_interest=payment.gross_interest,
                tax_withheld=payment.tax_withheld,
                net_interest=payment.net_interest,
                currency=payment.currency,
                bank_account_id=bank.id,
                bank_included_in_portfolio_scope=bank_included,
                should_count_as_attributed_income=not bank_included,
            )
        )
    return events


def _convert_attributed_amounts(
    events: list[FdAttributedIncomeEvent],
    calculation_currency: str,
) -> tuple[dict[date, Decimal], list[str], Optional[date]]:
    calc_ccy = norm_display_currency(calculation_currency)
    countable = [e for e in events if e.should_count_as_attributed_income]
    if not countable:
        return {}, [], None

    fx_pairs: set[tuple[str, str]] = set()
    for event in countable:
        ccy = (event.currency or calc_ccy).strip().upper()
        if ccy != calc_ccy:
            fx_pairs.add((ccy, calc_ccy))

    flow_dates = [e.payment_date for e in countable]
    fx_start = min(flow_dates) - timedelta(days=FX_LOOKBACK_DAYS)
    fx_end = max(flow_dates)
    fx_maps = load_fx_rate_maps(fx_pairs, fx_start, fx_end) if fx_pairs else {}

    by_date: dict[date, Decimal] = {}
    warnings: list[str] = []
    unknown_from: Optional[date] = None
    for event in countable:
        native = Decimal(event.net_interest)
        ccy = (event.currency or calc_ccy).strip().upper()
        if ccy == calc_ccy:
            converted = native
        else:
            converted, _ = convert_amount_with_fill_from_maps(
                native, ccy, calc_ccy, event.payment_date, fx_maps
            )
            if converted is None:
                unknown_from = (
                    min(unknown_from, event.payment_date)
                    if unknown_from
                    else event.payment_date
                )
                continue
            native = converted
        by_date[event.payment_date] = by_date.get(event.payment_date, Decimal("0")) + native

    if unknown_from is not None:
        warnings.append(FD_ATTRIBUTED_INCOME_FX_WARNING)
    return by_date, warnings, unknown_from


def build_fd_attributed_income_by_date(
    user: AbstractBaseUser,
    scope: ResolvedPortfolioScope,
    *,
    calculation_currency: str,
) -> tuple[dict[date, Decimal], list[str], Optional[date]]:
    """Net attributed FD income by payment date (excludes bank-included double count)."""
    events = list_fd_attributed_income_events(user, scope)
    return _convert_attributed_amounts(events, calculation_currency)


def build_fd_attributed_xirr_flows(
    user: AbstractBaseUser,
    scope: ResolvedPortfolioScope,
    *,
    calculation_currency: str,
) -> tuple[dict[date, Decimal], bool]:
    """
    Positive investor-perspective XIRR flows for attributed FD income.

    Used when bank cash is excluded — interest already in terminal when bank included.
    """
    by_date, _, unknown_from = build_fd_attributed_income_by_date(
        user, scope, calculation_currency=calculation_currency
    )
    return by_date, unknown_from is not None


def _cumulative_attributed_through(
    income_by_date: dict[date, Decimal],
    as_of: date,
) -> Decimal:
    total = Decimal("0")
    for payment_date, amount in income_by_date.items():
        if payment_date <= as_of:
            total += amount
    return total


def merge_fd_attributed_income_into_return_timeseries(
    timeseries: list[dict],
    *,
    user: AbstractBaseUser,
    scope: ResolvedPortfolioScope,
    display_currency: str,
    start_date: date,
    end_date: date,
) -> tuple[list[dict], list[str]]:
    """
    Add cumulative portfolio-attributed FD net income to return PV series only.

    Does not affect summary ``current_value`` (holdings wealth). Improves TWROR /
    cumulative return when interest was paid to excluded external bank accounts.
    """
    if user is None:
        return timeseries, []

    income_by_date, warnings, _ = build_fd_attributed_income_by_date(
        user, scope, calculation_currency=display_currency
    )
    if not income_by_date:
        return timeseries, warnings

    if not timeseries:
        out: list[dict] = []
        for day in sorted(income_by_date):
            if day < start_date or day > end_date:
                continue
            cum = _cumulative_attributed_through(income_by_date, day)
            if cum <= 0:
                continue
            out.append(
                {
                    "date": day.isoformat(),
                    "portfolio_value": float(cum),
                    "invested_amount": 0.0,
                    "fx_status": "ok",
                }
            )
        return out, warnings

    out: list[dict] = []
    for row in timeseries:
        day_str = row["date"]
        day = date.fromisoformat(day_str)
        if day < start_date or day > end_date:
            out.append(dict(row))
            continue
        merged = dict(row)
        pv = merged.get("portfolio_value")
        if pv is not None:
            cum = _cumulative_attributed_through(income_by_date, day)
            merged["portfolio_value"] = float(Decimal(str(pv)) + cum)
        out.append(merged)
    return out, warnings
