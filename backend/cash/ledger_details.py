"""Human-readable cash ledger row details for API display (CASH-UI-1)."""

from __future__ import annotations

from decimal import Decimal

from cash.models import CashEntryType, CashLedgerEntry
from finance.cash import mf_sell_cash_proceeds, stock_sell_cash_proceeds
from transactions.models import MutualFundTransactionDetail, TransactionType


def _fmt_decimal(value: Decimal | None, *, places: int = 2) -> str:
    if value is None:
        return ""
    quant = Decimal(10) ** -places
    normalized = value.quantize(quant)
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _fmt_money(value: Decimal | None, currency: str) -> str:
    if value is None:
        return ""
    return f"{_fmt_decimal(value)} {currency}"


def _join_parts(parts: list[str]) -> str:
    cleaned = [p.strip() for p in parts if p and p.strip()]
    return " · ".join(cleaned)


def _manual_entry_details(entry: CashLedgerEntry) -> str:
    parts: list[str] = []
    if entry.source_of_funds:
        parts.append(entry.source_of_funds.strip())
    if entry.note:
        parts.append(entry.note.strip())
    if parts:
        return _join_parts(parts)
    if entry.entry_type == CashEntryType.CASH_DEPOSIT:
        return "Cash deposit"
    if entry.entry_type == CashEntryType.CASH_WITHDRAWAL:
        return "Cash withdrawal"
    return "Manual cash entry"


def _stock_calculated_proceeds(txn) -> Decimal | None:
    if txn.type != TransactionType.SELL:
        return None
    return stock_sell_cash_proceeds(
        txn.quantity, txn.price_per_share or Decimal("0"), txn.fees
    )


def _stock_settlement_details(entry: CashLedgerEntry, txn) -> str:
    action = "Buy" if entry.entry_type == CashEntryType.BUY_SETTLEMENT else "Sell"
    parts = [
        f"{action} {txn.asset_symbol}",
        f"Qty {_fmt_decimal(txn.quantity, places=4)}",
    ]
    if txn.price_per_share is not None:
        parts.append(f"Price {_fmt_money(txn.price_per_share, txn.currency)}")
    if entry.entry_type == CashEntryType.SELL_SETTLEMENT:
        calculated = _stock_calculated_proceeds(txn)
        if calculated is not None:
            parts.append(f"Calculated proceeds {_fmt_money(calculated, txn.currency)}")
    elif txn.fees and txn.fees != 0:
        parts.append(f"Fees {_fmt_money(txn.fees, txn.currency)}")
    return _join_parts(parts)


def _mf_calculated_proceeds(txn, detail: MutualFundTransactionDetail) -> Decimal | None:
    if txn.type != TransactionType.SELL:
        return None
    return mf_sell_cash_proceeds(
        paid_value=detail.paid_value,
        units_allotted=detail.units_allotted,
        nav=detail.nav,
        fees=txn.fees,
    )


def _mf_settlement_details(entry: CashLedgerEntry, txn, detail: MutualFundTransactionDetail) -> str:
    action = "Buy" if entry.entry_type == CashEntryType.BUY_SETTLEMENT else "Sell"
    folio_number = detail.folio.folio_number if detail.folio_id else ""
    parts = [
        f"{action} {txn.asset_symbol}",
    ]
    if folio_number:
        parts.append(f"Folio {folio_number}")
    parts.append(f"Units {_fmt_decimal(detail.units_allotted, places=4)}")
    parts.append(f"NAV {_fmt_money(detail.nav, txn.currency)}")
    if entry.entry_type == CashEntryType.SELL_SETTLEMENT:
        calculated = _mf_calculated_proceeds(txn, detail)
        if calculated is not None:
            parts.append(f"Calculated proceeds {_fmt_money(calculated, txn.currency)}")
    else:
        parts.append(f"Paid {_fmt_money(detail.paid_value, txn.currency)}")
    return _join_parts(parts)


def _tax_withheld_details(entry: CashLedgerEntry, txn) -> str:
    try:
        detail = txn.mutual_fund_detail
    except MutualFundTransactionDetail.DoesNotExist:
        detail = None

    if detail is not None:
        calculated = _mf_calculated_proceeds(txn, detail)
        symbol = txn.asset_symbol
        folio_number = detail.folio.folio_number if detail.folio_id else ""
        headline = f"Tax withheld / broker adjustment for SELL {symbol}"
        if folio_number:
            headline = f"{headline} · Folio {folio_number}"
    else:
        calculated = _stock_calculated_proceeds(txn)
        headline = f"Tax withheld / broker adjustment for SELL {txn.asset_symbol}"

    actual = txn.actual_cash_received
    parts = [headline]
    if calculated is not None:
        parts.append(f"Calculated {_fmt_money(calculated, txn.currency)}")
    if actual is not None:
        parts.append(f"Actual received {_fmt_money(actual, txn.currency)}")
    if calculated is not None and actual is not None:
        withheld = calculated - actual
        if withheld > 0:
            parts.append(f"Withheld {_fmt_money(withheld, txn.currency)}")
    note = (entry.note or txn.settlement_note or "").strip()
    if note:
        parts.append(note)
    return _join_parts(parts)


def _transfer_details(entry: CashLedgerEntry) -> str:
    group = entry.transfer_group
    if group is None:
        return entry.note.strip() if entry.note else "Portfolio transfer"

    src_name = group.source_portfolio.name
    tgt_name = group.target_portfolio.name
    same_currency = group.source_currency == group.target_currency

    if entry.entry_type == CashEntryType.TRANSFER_OUT:
        headline = f"Transfer to {tgt_name}"
    elif entry.entry_type == CashEntryType.TRANSFER_IN:
        headline = f"Transfer from {src_name}"
    else:
        headline = "Portfolio transfer"

    if same_currency:
        amount = (
            group.source_amount
            if entry.entry_type == CashEntryType.TRANSFER_OUT
            else group.target_amount
        )
        return _join_parts(
            [headline, _fmt_money(amount, group.source_currency)]
        )

    if entry.entry_type == CashEntryType.TRANSFER_OUT:
        leg = _fmt_money(group.source_amount, group.source_currency)
        received = _fmt_money(group.target_amount, group.target_currency)
        return _join_parts([headline, f"{leg} → {received}"])
    leg = _fmt_money(group.target_amount, group.target_currency)
    sent = _fmt_money(group.source_amount, group.source_currency)
    return _join_parts([headline, f"{sent} → {leg}"])


def _fx_conversion_details(entry: CashLedgerEntry) -> str:
    if entry.note:
        return entry.note.strip()
    if entry.entry_type == CashEntryType.FX_CONVERSION_OUT:
        return "FX conversion out"
    if entry.entry_type == CashEntryType.FX_CONVERSION_IN:
        return "FX conversion in"
    return "FX conversion"


def _fallback_details(entry: CashLedgerEntry) -> str:
    if entry.note:
        return entry.note.strip()
    label = entry.get_entry_type_display()
    return label if label else "Cash ledger entry"


def build_ledger_entry_details(entry: CashLedgerEntry) -> str:
    """Build a single human-readable details string from persisted ledger data."""
    entry_type = entry.entry_type

    if entry_type in {CashEntryType.CASH_DEPOSIT, CashEntryType.CASH_WITHDRAWAL}:
        if entry.linked_transaction_id is None and entry.transfer_group_id is None:
            return _manual_entry_details(entry)

    txn = entry.linked_transaction
    if txn is not None and entry_type == CashEntryType.TAX_WITHHELD:
        return _tax_withheld_details(entry, txn)

    if txn is not None and entry_type in {
        CashEntryType.BUY_SETTLEMENT,
        CashEntryType.SELL_SETTLEMENT,
    }:
        try:
            detail = txn.mutual_fund_detail
        except MutualFundTransactionDetail.DoesNotExist:
            detail = None
        if detail is not None:
            return _mf_settlement_details(entry, txn, detail)
        if txn.type in {TransactionType.BUY, TransactionType.SELL}:
            return _stock_settlement_details(entry, txn)
        if entry.note:
            return entry.note.strip()
        return _fallback_details(entry)

    if entry_type in {CashEntryType.TRANSFER_OUT, CashEntryType.TRANSFER_IN}:
        return _transfer_details(entry)

    if entry_type in {CashEntryType.FX_CONVERSION_OUT, CashEntryType.FX_CONVERSION_IN}:
        return _fx_conversion_details(entry)

    if entry_type in {
        CashEntryType.DIVIDEND_CASH,
        CashEntryType.INTEREST,
        CashEntryType.FEE,
        CashEntryType.TAX,
        CashEntryType.ADJUSTMENT,
    }:
        if entry.note:
            return entry.note.strip()
        return _fallback_details(entry)

    return _fallback_details(entry)
