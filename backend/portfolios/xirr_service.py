"""Portfolio-level XIRR: legacy transaction flows vs cash-aware ledger flows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from cash.services import build_cash_display_summary
from debt.cash_ledger_flows import build_bank_cash_xirr_external_flows
from debt.portfolio_value import (
    calculate_bank_cash_for_scope,
    calculate_fd_holdings_for_scope,
)
from portfolios.cash_ledger_flows import build_cash_aware_xirr_external_flows
from finance.mutual_fund_cashflows import build_legacy_portfolio_xirr_flows
from finance.splits import apply_stock_split_adjustments
from finance.xirr import solve_xirr
from fx.lookup import convert_amount_with_fill_from_maps, load_fx_rate_maps
from portfolios import dates as portfolio_dates
from portfolios.models import Portfolio
from portfolios.scope import ResolvedPortfolioScope
from portfolios.summary_service import (
    _calculate_holdings,
    _calculate_mf_holdings,
    _fifo_eligible_queryset,
    _merge_holdings_results,
    _mf_cashflow_events,
    _portfolio_base_currency,
    _to_fifo_dtos,
    _transactions_by_symbol,
    norm_display_currency,
    transactions_by_mf_holding,
)

FX_LOOKBACK_DAYS = 7

XIRR_FX_WARNING = (
    "FX rates are missing for one or more portfolio XIRR cash flows; XIRR is unavailable."
)

@dataclass(frozen=True)
class ScopeXirrResult:
    value: Optional[float]
    warnings: list[str]


@dataclass(frozen=True)
class _PortfolioXirrInputs:
    flows_by_date: dict[date, Decimal]
    terminal_value: Decimal
    fx_missing: bool
    warnings: list[str]


def _holdings_terminal_for_scope(
    scope: ResolvedPortfolioScope,
    *,
    portfolio_base: str,
) -> Decimal:
    queryset = _fifo_eligible_queryset(scope.portfolio_ids)
    all_txns = list(queryset)
    if not all_txns:
        return Decimal("0")
    by_symbol = _transactions_by_symbol(queryset)
    by_mf = transactions_by_mf_holding(queryset)
    stock = _calculate_holdings(by_symbol)
    mf = _calculate_mf_holdings(by_mf, portfolio_base=portfolio_base)
    return _merge_holdings_results(stock, mf).current_value


def _convert_amount(
    amount: Decimal,
    *,
    from_currency: str,
    to_currency: str,
    conv_date: date,
) -> tuple[Decimal | None, bool]:
    src = norm_display_currency(from_currency)
    dst = norm_display_currency(to_currency)
    if src == dst:
        return amount, False
    fx_start = conv_date - timedelta(days=FX_LOOKBACK_DAYS)
    fx_maps = load_fx_rate_maps({(src, dst)}, fx_start, conv_date)
    converted, _ = convert_amount_with_fill_from_maps(
        amount, src, dst, conv_date, fx_maps
    )
    if converted is None:
        return None, True
    return converted, False


def _build_legacy_transaction_flows(
    scope: ResolvedPortfolioScope,
    *,
    calculation_currency: str,
) -> tuple[dict[date, Decimal], bool]:
    queryset = _fifo_eligible_queryset(scope.portfolio_ids)
    all_txns = list(queryset)
    if not all_txns:
        return {}, False

    by_symbol = _transactions_by_symbol(queryset)
    stock_cashflow_txns = []
    for txns in by_symbol.values():
        stock_cashflow_txns.extend(apply_stock_split_adjustments(_to_fifo_dtos(txns)))
    mf_events = _mf_cashflow_events(all_txns)
    portfolio_base = _portfolio_base_currency(all_txns)

    return build_legacy_portfolio_xirr_flows(
        stock_cashflow_txns,
        mf_events,
        portfolio_base=portfolio_base,
        calculation_currency=calculation_currency,
    )


def _fd_terminal_for_scope(
    scope: ResolvedPortfolioScope,
    *,
    calculation_currency: str,
    today: date,
) -> tuple[Decimal, bool, list[str]]:
    fd = calculate_fd_holdings_for_scope(
        scope, display_currency=calculation_currency, as_of_date=today
    )
    return fd.current_value, fd.any_fx_missing, list(fd.warnings)


def _bank_terminal_for_scope(
    user,
    scope: ResolvedPortfolioScope,
    *,
    calculation_currency: str,
    today: date,
) -> tuple[Decimal, bool, list[str]]:
    if user is None:
        return Decimal("0"), False, []
    bank = calculate_bank_cash_for_scope(
        user, scope, display_currency=calculation_currency, as_of_date=today
    )
    return bank.current_value, bank.any_fx_missing, list(bank.warnings)


def _merge_xirr_flow_maps(
    parts: list[tuple[dict[date, Decimal], bool]],
) -> tuple[dict[date, Decimal], bool]:
    merged: dict[date, Decimal] = {}
    fx_missing = False
    for flows, part_fx_missing in parts:
        fx_missing = fx_missing or part_fx_missing
        for d, amt in flows.items():
            merged[d] = merged.get(d, Decimal("0")) + amt
    return merged, fx_missing


def _portfolio_xirr_inputs(
    portfolio: Portfolio,
    *,
    calculation_currency: str,
    today: date,
    user=None,
    include_bank_terminal: bool = False,
    include_bank_flows: bool = False,
) -> _PortfolioXirrInputs:
    child_scope = ResolvedPortfolioScope(
        kind="single", portfolio_ids=[portfolio.id]
    )
    queryset = _fifo_eligible_queryset(child_scope.portfolio_ids)
    all_txns = list(queryset)
    calc_ccy = norm_display_currency(calculation_currency)
    portfolio_base = _portfolio_base_currency(all_txns) if all_txns else calc_ccy

    flow_parts: list[tuple[dict[date, Decimal], bool]] = []
    if portfolio.cash_aware_enabled:
        broker_flows, broker_fx_missing = build_cash_aware_xirr_external_flows(
            portfolio.id, calculation_currency=calc_ccy
        )
        flow_parts.append((broker_flows, broker_fx_missing))
        holdings_terminal = _holdings_terminal_for_scope(
            child_scope, portfolio_base=portfolio_base
        )
        holdings_in_calc, holdings_fx_missing = _convert_amount(
            holdings_terminal,
            from_currency=portfolio_base,
            to_currency=calc_ccy,
            conv_date=today,
        )
        cash_summary = build_cash_display_summary(
            child_scope, calc_ccy, as_of_date=today
        )
        cash_fx_missing = (
            cash_summary.fx_status == "fx_unavailable"
            and cash_summary.totals_by_currency
            and any(bal != 0 for _, bal in cash_summary.totals_by_currency)
        )
        terminal = (holdings_in_calc or Decimal("0")) + cash_summary.total_display_value
        warnings = list(cash_summary.warnings)
        if holdings_fx_missing:
            holdings_in_calc = None
    else:
        legacy_flows, legacy_fx_missing = _build_legacy_transaction_flows(
            child_scope, calculation_currency=calc_ccy
        )
        flow_parts.append((legacy_flows, legacy_fx_missing))
        holdings_terminal = _holdings_terminal_for_scope(
            child_scope, portfolio_base=portfolio_base
        )
        holdings_in_calc, holdings_fx_missing = _convert_amount(
            holdings_terminal,
            from_currency=portfolio_base,
            to_currency=calc_ccy,
            conv_date=today,
        )
        cash_fx_missing = False
        warnings = []
        terminal = holdings_in_calc or Decimal("0")

    fd_terminal, fd_fx_missing, fd_warnings = _fd_terminal_for_scope(
        child_scope, calculation_currency=calc_ccy, today=today
    )
    terminal += fd_terminal
    warnings.extend(fd_warnings)

    bank_fx_missing = False
    if include_bank_terminal and user is not None:
        bank_terminal, bank_fx_missing, bank_warnings = _bank_terminal_for_scope(
            user, child_scope, calculation_currency=calc_ccy, today=today
        )
        terminal += bank_terminal
        warnings.extend(bank_warnings)

    if include_bank_flows and user is not None:
        bank_flows, bank_flows_fx_missing = build_bank_cash_xirr_external_flows(
            user, child_scope, calculation_currency=calc_ccy
        )
        flow_parts.append((bank_flows, bank_flows_fx_missing))

    flows_by_date, flows_fx_missing = _merge_xirr_flow_maps(flow_parts)

    combined_fx_missing = (
        flows_fx_missing
        or holdings_fx_missing
        or cash_fx_missing
        or fd_fx_missing
        or bank_fx_missing
        or holdings_in_calc is None
    )
    return _PortfolioXirrInputs(
        flows_by_date=flows_by_date,
        terminal_value=terminal,
        fx_missing=combined_fx_missing,
        warnings=warnings,
    )


def _solve_from_inputs(
    inputs: _PortfolioXirrInputs,
    *,
    today: date,
) -> ScopeXirrResult:
    if inputs.fx_missing:
        return ScopeXirrResult(
            value=None,
            warnings=list(dict.fromkeys(inputs.warnings + [XIRR_FX_WARNING])),
        )
    dates = sorted(inputs.flows_by_date.keys())
    amounts = [float(inputs.flows_by_date[d]) for d in dates]
    if inputs.terminal_value > 0 or amounts:
        dates.append(today)
        amounts.append(float(inputs.terminal_value))
    if not dates:
        return ScopeXirrResult(value=None, warnings=inputs.warnings)
    return ScopeXirrResult(
        value=solve_xirr(dates, amounts),
        warnings=list(dict.fromkeys(inputs.warnings)),
    )


def compute_scope_xirr_detail(
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str | None = None,
    user=None,
) -> ScopeXirrResult:
    """
    Money-weighted portfolio XIRR for the full scope (inception through today).

    Legacy portfolios: BUY/SELL (+ MF paid_value) external flows; terminal = holdings
    + FD principal + included bank cash.
    Cash-aware portfolios: CASH_DEPOSIT / CASH_WITHDRAWAL (+ unlinked ADJUSTMENT);
    BUY/SELL settlements excluded; terminal = holdings + broker cash + FD + bank.
    Included bank cash: manual deposits/withdrawals/opening balance are external flows;
    FD system movements are internal (FD-ACC-8C).

    All Portfolios: per-portfolio rules above; flows converted to ``display_currency``
    and merged by date. Legacy and cash-aware portfolios may be mixed.
    """
    today = portfolio_dates.current_date()

    if scope.kind == "all_active":
        calc_ccy = norm_display_currency(display_currency or "EUR")
        portfolios = {
            p.id: p
            for p in Portfolio.objects.filter(pk__in=scope.portfolio_ids).only(
                "id", "cash_aware_enabled"
            )
        }
        merged_flows: dict[date, Decimal] = {}
        terminal_total = Decimal("0")
        warnings: list[str] = []
        any_fx_block = False

        for portfolio_id in scope.portfolio_ids:
            portfolio = portfolios.get(portfolio_id)
            if portfolio is None:
                continue
            inputs = _portfolio_xirr_inputs(
                portfolio,
                calculation_currency=calc_ccy,
                today=today,
                user=user,
                include_bank_terminal=False,
                include_bank_flows=False,
            )
            warnings.extend(inputs.warnings)
            if inputs.fx_missing:
                any_fx_block = True
                continue
            for d, amt in inputs.flows_by_date.items():
                merged_flows[d] = merged_flows.get(d, Decimal("0")) + amt
            terminal_total += inputs.terminal_value

        if user is not None:
            bank_terminal, bank_fx_missing, bank_warnings = _bank_terminal_for_scope(
                user, scope, calculation_currency=calc_ccy, today=today
            )
            bank_flows, bank_flows_fx_missing = build_bank_cash_xirr_external_flows(
                user, scope, calculation_currency=calc_ccy
            )
            warnings.extend(bank_warnings)
            if bank_fx_missing or bank_flows_fx_missing:
                any_fx_block = True
            else:
                terminal_total += bank_terminal
                for d, amt in bank_flows.items():
                    merged_flows[d] = merged_flows.get(d, Decimal("0")) + amt

        if any_fx_block:
            return ScopeXirrResult(
                value=None,
                warnings=list(dict.fromkeys(warnings + [XIRR_FX_WARNING])),
            )

        combined = _PortfolioXirrInputs(
            flows_by_date=merged_flows,
            terminal_value=terminal_total,
            fx_missing=False,
            warnings=warnings,
        )
        return _solve_from_inputs(combined, today=today)

    portfolio_id = scope.portfolio_ids[0]
    portfolio = Portfolio.objects.filter(pk=portfolio_id).first()
    if portfolio is None:
        return ScopeXirrResult(value=None, warnings=[])

    queryset = _fifo_eligible_queryset(scope.portfolio_ids)
    all_txns = list(queryset)
    calc_ccy = (
        _portfolio_base_currency(all_txns)
        if all_txns
        else norm_display_currency(display_currency or "EUR")
    )
    inputs = _portfolio_xirr_inputs(
        portfolio,
        calculation_currency=calc_ccy,
        today=today,
        user=user,
        include_bank_terminal=True,
        include_bank_flows=True,
    )
    return _solve_from_inputs(inputs, today=today)


def compute_scope_xirr(
    scope: ResolvedPortfolioScope,
    *,
    display_currency: str | None = None,
    user=None,
) -> Optional[float]:
    """Return annualized XIRR or None (see ``compute_scope_xirr_detail`` for warnings)."""
    return compute_scope_xirr_detail(
        scope, display_currency=display_currency, user=user
    ).value
