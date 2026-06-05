"""Cash ledger entry classification and external-flow amounts (TWROR / XIRR)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from cash.models import CashEntryType, CashLedgerEntry
from portfolios.summary_service import norm_display_currency
from fx.lookup import convert_amount_with_fill_from_maps, load_fx_rate_maps

FX_LOOKBACK_DAYS = 7

CASH_AWARE_EXTERNAL_ENTRY_TYPES = frozenset(
    {
        CashEntryType.CASH_DEPOSIT,
        CashEntryType.CASH_WITHDRAWAL,
    }
)

CASH_AWARE_INTERNAL_ENTRY_TYPES = frozenset(
    {
        CashEntryType.BUY_SETTLEMENT,
        CashEntryType.SELL_SETTLEMENT,
        CashEntryType.DIVIDEND_CASH,
        CashEntryType.INTEREST,
        CashEntryType.FEE,
        CashEntryType.TAX,
        CashEntryType.TRANSFER_OUT,
        CashEntryType.TRANSFER_IN,
        CashEntryType.FX_CONVERSION_OUT,
        CashEntryType.FX_CONVERSION_IN,
    }
)


def is_cash_aware_external_ledger_entry(entry: CashLedgerEntry) -> bool:
    if entry.linked_transaction_id is not None:
        return False
    if entry.transfer_group_id is not None:
        return False
    if entry.entry_type in CASH_AWARE_INTERNAL_ENTRY_TYPES:
        return False
    if entry.entry_type in CASH_AWARE_EXTERNAL_ENTRY_TYPES:
        return True
    if entry.entry_type == CashEntryType.ADJUSTMENT:
        return True
    return False


def twror_flow_amount_from_ledger(entry: CashLedgerEntry) -> Decimal:
    """
    TWROR external flow in native ledger currency.

    Positive = contribution (``CASH_DEPOSIT``), negative = withdrawal.
    Uses signed ``entry.amount`` (deposit +, withdrawal −).
    """
    return entry.amount


def xirr_flow_amount_from_ledger(entry: CashLedgerEntry) -> Decimal:
    """Investor-perspective XIRR flow (deposit negative, withdrawal positive)."""
    return -entry.amount


def build_cash_aware_external_flows(
    portfolio_id: int,
    *,
    calculation_currency: str,
    amount_mapper,
) -> tuple[dict[date, Decimal], Optional[date]]:
    """
    External cash-ledger flows by date in ``calculation_currency``.

    ``amount_mapper`` maps each entry to a signed native amount (TWROR or XIRR convention).
    Returns ``(flows_by_date, flows_unknown_from)`` where ``flows_unknown_from`` is the
    earliest date with a flow that could not be FX-converted.
    """
    entries = CashLedgerEntry.objects.filter(portfolio_id=portfolio_id).order_by(
        "date", "id"
    )
    external = [e for e in entries if is_cash_aware_external_ledger_entry(e)]
    if not external:
        return {}, None

    calc_ccy = norm_display_currency(calculation_currency)
    flow_dates = [e.date for e in external]
    fx_pairs: set[tuple[str, str]] = set()
    for entry in external:
        ccy = (entry.currency or calc_ccy).strip().upper()
        if ccy != calc_ccy:
            fx_pairs.add((ccy, calc_ccy))

    fx_start = min(flow_dates) - timedelta(days=FX_LOOKBACK_DAYS)
    fx_end = max(flow_dates)
    fx_maps = load_fx_rate_maps(fx_pairs, fx_start, fx_end) if fx_pairs else {}

    flows_by_date: dict[date, Decimal] = {}
    flows_unknown_from: Optional[date] = None
    for entry in external:
        native = amount_mapper(entry)
        ccy = (entry.currency or calc_ccy).strip().upper()
        if ccy == calc_ccy:
            converted = native
        else:
            converted, _ = convert_amount_with_fill_from_maps(
                native,
                ccy,
                calc_ccy,
                entry.date,
                fx_maps,
            )
            if converted is None:
                flows_unknown_from = (
                    min(flows_unknown_from, entry.date)
                    if flows_unknown_from
                    else entry.date
                )
                continue
            native = converted
        flows_by_date[entry.date] = flows_by_date.get(entry.date, Decimal("0")) + native

    return flows_by_date, flows_unknown_from


def build_cash_aware_twror_external_flows(
    portfolio_id: int,
    *,
    calculation_currency: str,
) -> tuple[dict[date, Decimal], Optional[date]]:
    return build_cash_aware_external_flows(
        portfolio_id,
        calculation_currency=calculation_currency,
        amount_mapper=twror_flow_amount_from_ledger,
    )


def build_cash_aware_xirr_external_flows(
    portfolio_id: int,
    *,
    calculation_currency: str,
) -> tuple[dict[date, Decimal], bool]:
    """XIRR helper returns ``(flows_by_date, fx_missing)`` for compatibility."""
    flows, unknown = build_cash_aware_external_flows(
        portfolio_id,
        calculation_currency=calculation_currency,
        amount_mapper=xirr_flow_amount_from_ledger,
    )
    return flows, unknown is not None
