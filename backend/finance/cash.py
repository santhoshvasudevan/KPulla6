"""Pure cash ledger balance helpers (no Django imports)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Mapping

_ZERO = Decimal("0")


@dataclass(frozen=True)
class CashLedgerPoint:
    """Framework-independent cash ledger row for balance math."""

    date: date
    currency: str
    amount: Decimal  # signed: positive increases cash, negative decreases


def cash_balance_by_currency(
    entries: Iterable[CashLedgerPoint],
) -> dict[str, Decimal]:
    """Sum signed amounts per currency (all dates)."""
    balances: dict[str, Decimal] = {}
    for entry in entries:
        balances[entry.currency] = balances.get(entry.currency, _ZERO) + entry.amount
    return balances


def cash_balance_on_date(
    entries: Iterable[CashLedgerPoint],
    as_of_date: date,
) -> dict[str, Decimal]:
    """Per-currency balance including entries with ``date <= as_of_date``."""
    filtered = (e for e in entries if e.date <= as_of_date)
    return cash_balance_by_currency(filtered)


def cash_balance_timeseries(
    entries: Iterable[CashLedgerPoint],
    start_date: date,
    end_date: date,
) -> dict[str, list[tuple[date, Decimal]]]:
    """
    Per-currency end-of-day balances for each calendar day in [start_date, end_date].

    Opening balance on ``start_date`` includes entries dated before ``start_date``.
    Days without ledger activity carry forward the prior balance.
    """
    if end_date < start_date:
        return {}

    all_points = list(entries)
    currencies = {e.currency for e in all_points}
    if not currencies:
        return {}

    opening = cash_balance_on_date(all_points, start_date - timedelta(days=1))
    in_window = sorted(
        (e for e in all_points if start_date <= e.date <= end_date),
        key=lambda e: (e.currency, e.date),
    )

    running: dict[str, Decimal] = {
        c: opening.get(c, _ZERO) for c in currencies
    }
    pending: dict[str, list[tuple[date, Decimal]]] = {c: [] for c in currencies}
    idx = 0
    n = len(in_window)

    current = start_date
    while current <= end_date:
        while idx < n and in_window[idx].date == current:
            c = in_window[idx].currency
            running[c] = running.get(c, _ZERO) + in_window[idx].amount
            idx += 1
        for c in currencies:
            pending[c].append((current, running.get(c, _ZERO)))
        current += timedelta(days=1)

    return pending


def has_sufficient_cash(
    entries: Iterable[CashLedgerPoint],
    currency: str,
    required_amount: Decimal,
    as_of_date: date,
) -> bool:
    """True when balance in ``currency`` on ``as_of_date`` is >= ``required_amount``."""
    if required_amount <= 0:
        return True
    balances = cash_balance_on_date(entries, as_of_date)
    return balances.get(currency, _ZERO) >= required_amount


def stock_buy_cash_required(
    quantity: Decimal,
    price_per_share: Decimal,
    fees: Decimal,
) -> Decimal:
    """Positive cash need for a stock/ETF BUY settlement."""
    return quantity * price_per_share + fees


def stock_sell_cash_proceeds(
    quantity: Decimal,
    price_per_share: Decimal,
    fees: Decimal,
) -> Decimal:
    """Positive cash credited for a stock/ETF SELL settlement (gross minus fees)."""
    return quantity * price_per_share - fees


def mf_buy_cash_required(paid_value: Decimal) -> Decimal:
    """Positive cash need for a mutual fund BUY (uses paid_value, not qty × NAV)."""
    return paid_value


def sell_actual_cash_received(
    calculated_proceeds: Decimal,
    actual_cash_received: Decimal | None,
) -> Decimal:
    """Net cash credited after optional tax withholding; defaults to calculated proceeds."""
    if actual_cash_received is None:
        return calculated_proceeds
    return actual_cash_received


def sell_tax_withheld_amount(
    calculated_proceeds: Decimal,
    actual_cash_received: Decimal | None,
) -> Decimal:
    """Positive withheld/adjustment when actual received is below calculated proceeds."""
    actual = sell_actual_cash_received(calculated_proceeds, actual_cash_received)
    gap = calculated_proceeds - actual
    return gap if gap > 0 else _ZERO


def mf_sell_cash_proceeds(
    *,
    paid_value: Decimal,
    units_allotted: Decimal,
    nav: Decimal,
    fees: Decimal,
) -> Decimal:
    """
    Positive cash credited for MF SELL.

    Uses ``paid_value`` when > 0; otherwise ``units_allotted * nav - fees``.
    """
    if paid_value > 0:
        return paid_value
    return units_allotted * nav - fees


def cash_shortfall(
    entries: Iterable[CashLedgerPoint],
    currency: str,
    required_amount: Decimal,
    as_of_date: date,
) -> Decimal:
    """
    Shortfall in ``currency`` when insufficient; ``Decimal('0')`` when sufficient.

    ``required_amount`` is a positive cash need (e.g. buy settlement).
    """
    if required_amount <= 0:
        return _ZERO
    balances = cash_balance_on_date(entries, as_of_date)
    available = balances.get(currency, _ZERO)
    gap = required_amount - available
    return gap if gap > 0 else _ZERO


def cash_balances_as_mapping(
    balances: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Return a plain dict copy (helper for service layers)."""
    return dict(balances)
