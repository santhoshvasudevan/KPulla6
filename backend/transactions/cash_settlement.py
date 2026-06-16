"""Cash-aware BUY/SELL settlement ledger rows linked to asset transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_CASH_AMOUNT_QUANT = Decimal("0.0001")

from django.db import transaction as db_transaction

from cash.models import CashEntryType, CashLedgerEntry
from cash.services import (
    assert_delete_entries_would_not_make_cash_negative,
    assert_delete_settlement_would_not_make_cash_negative,
    assert_sufficient_cash_for_purchase,
    validate_cash_currency,
)
from finance.cash import (
    mf_buy_cash_required,
    mf_sell_cash_proceeds,
    sell_tax_withheld_amount,
    stock_buy_cash_required,
    stock_sell_cash_proceeds,
)
from portfolios.models import Portfolio
from transactions.models import MutualFundTransactionDetail, Transaction, TransactionType


def _validation_error(message: str):
    from transactions.services import TransactionValidationError

    return TransactionValidationError(message)


@dataclass(frozen=True)
class SettlementSpec:
    """Desired settlement row for a transaction, or none."""

    entry_type: str | None
    amount: Decimal | None
    ledger_date: date | None
    currency: str | None
    note: str = ""


def _quantize_cash_amount(value: Decimal) -> Decimal:
    return value.quantize(_CASH_AMOUNT_QUANT, rounding=ROUND_HALF_UP)


def _settlement_note(txn: Transaction) -> str:
    return f"{txn.type} {txn.asset_symbol}"


def _tax_withheld_note(txn: Transaction) -> str:
    note = (txn.settlement_note or "").strip()
    return note


def _stock_calculated_proceeds(txn: Transaction) -> Decimal:
    proceeds = stock_sell_cash_proceeds(
        txn.quantity, txn.price_per_share or Decimal("0"), txn.fees
    )
    if proceeds <= 0:
        raise _validation_error("SELL proceeds must be greater than zero after fees")
    return _quantize_cash_amount(proceeds)


def _mf_calculated_proceeds(
    txn: Transaction, detail: MutualFundTransactionDetail
) -> Decimal:
    proceeds = mf_sell_cash_proceeds(
        paid_value=detail.paid_value,
        units_allotted=detail.units_allotted,
        nav=detail.nav,
        fees=txn.fees,
    )
    if proceeds <= 0:
        raise _validation_error("SELL proceeds must be greater than zero")
    return _quantize_cash_amount(proceeds)


def _sell_settlement_specs(
    txn: Transaction,
    *,
    calculated_proceeds: Decimal,
    ledger_date: date,
    currency: str,
) -> list[SettlementSpec]:
    note = _settlement_note(txn)
    specs = [
        SettlementSpec(
            CashEntryType.SELL_SETTLEMENT,
            calculated_proceeds,
            ledger_date,
            currency,
            note,
        )
    ]
    withheld = sell_tax_withheld_amount(calculated_proceeds, txn.actual_cash_received)
    if withheld > 0:
        specs.append(
            SettlementSpec(
                CashEntryType.TAX_WITHHELD,
                -_quantize_cash_amount(withheld),
                ledger_date,
                currency,
                _tax_withheld_note(txn),
            )
        )
    return specs


def _stock_settlement_specs(txn: Transaction) -> list[SettlementSpec]:
    if txn.type in {TransactionType.STOCK_SPLIT, TransactionType.DIVIDEND}:
        return []

    currency = validate_cash_currency(txn.currency)
    note = _settlement_note(txn)

    if txn.type == TransactionType.BUY:
        required = stock_buy_cash_required(
            txn.quantity, txn.price_per_share or Decimal("0"), txn.fees
        )
        return [
            SettlementSpec(
                CashEntryType.BUY_SETTLEMENT,
                -_quantize_cash_amount(required),
                txn.date,
                currency,
                note,
            )
        ]

    if txn.type == TransactionType.SELL:
        calculated = _stock_calculated_proceeds(txn)
        return _sell_settlement_specs(
            txn,
            calculated_proceeds=calculated,
            ledger_date=txn.date,
            currency=currency,
        )

    return []


def _mf_settlement_specs(
    txn: Transaction, detail: MutualFundTransactionDetail
) -> list[SettlementSpec]:
    currency = validate_cash_currency(txn.currency)
    note = _settlement_note(txn)
    ledger_date = detail.investment_date

    if txn.type == TransactionType.BUY:
        required = mf_buy_cash_required(detail.paid_value)
        return [
            SettlementSpec(
                CashEntryType.BUY_SETTLEMENT,
                -_quantize_cash_amount(required),
                ledger_date,
                currency,
                note,
            )
        ]

    if txn.type == TransactionType.SELL:
        calculated = _mf_calculated_proceeds(txn, detail)
        return _sell_settlement_specs(
            txn,
            calculated_proceeds=calculated,
            ledger_date=ledger_date,
            currency=currency,
        )

    return []


def _primary_settlement_spec(specs: list[SettlementSpec]) -> SettlementSpec:
    """First BUY/SELL settlement spec; empty spec when none apply."""
    for spec in specs:
        if spec.entry_type in (
            CashEntryType.BUY_SETTLEMENT,
            CashEntryType.SELL_SETTLEMENT,
        ):
            return spec
    return SettlementSpec(None, None, None, None)


def _stock_settlement_spec(txn: Transaction) -> SettlementSpec:
    """Primary settlement spec for stock/ETF transactions (sync/diagnostics)."""
    return _primary_settlement_spec(_stock_settlement_specs(txn))


def _mf_settlement_spec(
    txn: Transaction, detail: MutualFundTransactionDetail
) -> SettlementSpec:
    """Primary settlement spec for mutual fund transactions (sync/diagnostics)."""
    return _primary_settlement_spec(_mf_settlement_specs(txn, detail))


def _get_linked_settlement(txn: Transaction) -> CashLedgerEntry | None:
    """Primary linked BUY/SELL settlement row (excludes TAX_WITHHELD)."""
    return (
        CashLedgerEntry.objects.filter(
            linked_transaction_id=txn.pk,
            entry_type__in=(
                CashEntryType.BUY_SETTLEMENT,
                CashEntryType.SELL_SETTLEMENT,
            ),
        )
        .order_by("id")
        .first()
    )


def _delete_surplus_linked_entries(
    entries: list[CashLedgerEntry],
) -> None:
    sell_entries_to_check = [
        entry
        for entry in entries
        if entry.entry_type == CashEntryType.SELL_SETTLEMENT
    ]
    if sell_entries_to_check:
        assert_delete_entries_would_not_make_cash_negative(sell_entries_to_check)
    for entry in entries:
        entry.delete()


def _apply_settlement_spec(
    txn: Transaction,
    portfolio: Portfolio,
    spec: SettlementSpec,
    existing: CashLedgerEntry | None,
) -> None:
    assert spec.entry_type is not None
    assert spec.amount is not None
    assert spec.ledger_date is not None
    assert spec.currency is not None

    if spec.entry_type == CashEntryType.BUY_SETTLEMENT:
        required = abs(_quantize_cash_amount(spec.amount))
        assert_sufficient_cash_for_purchase(
            portfolio,
            spec.currency,
            required,
            spec.ledger_date,
            exclude_entry_id=existing.pk if existing else None,
        )

    if existing is not None:
        if (
            existing.entry_type == CashEntryType.SELL_SETTLEMENT
            and spec.entry_type != CashEntryType.SELL_SETTLEMENT
        ):
            assert_delete_settlement_would_not_make_cash_negative(existing)
        existing.portfolio = portfolio
        existing.date = spec.ledger_date
        existing.currency = spec.currency
        existing.entry_type = spec.entry_type
        existing.amount = spec.amount
        existing.note = spec.note
        existing.full_clean()
        existing.save()
        return

    entry = CashLedgerEntry(
        portfolio=portfolio,
        date=spec.ledger_date,
        currency=spec.currency,
        entry_type=spec.entry_type,
        amount=spec.amount,
        linked_transaction=txn,
        note=spec.note,
    )
    entry.full_clean()
    entry.save()


def _sync_settlement_specs(
    txn: Transaction,
    portfolio: Portfolio,
    specs: list[SettlementSpec],
) -> None:
    existing_list = list(
        CashLedgerEntry.objects.filter(linked_transaction_id=txn.pk).order_by("id")
    )
    existing_by_type = {entry.entry_type: entry for entry in existing_list}
    desired_types = {spec.entry_type for spec in specs if spec.entry_type is not None}
    surplus = [entry for entry in existing_list if entry.entry_type not in desired_types]

    morph_source: CashLedgerEntry | None = None
    if surplus and specs:
        morph_source = surplus[0]
        _delete_surplus_linked_entries(surplus[1:])
    elif surplus:
        _delete_surplus_linked_entries(surplus)

    for spec in specs:
        if spec.entry_type is None:
            continue
        existing = existing_by_type.get(spec.entry_type)
        if existing is None and morph_source is not None:
            existing = morph_source
            morph_source = None
        _apply_settlement_spec(txn, portfolio, spec, existing)

    if morph_source is not None:
        _delete_surplus_linked_entries([morph_source])


def sync_stock_settlement(txn: Transaction) -> None:
    portfolio = Portfolio.objects.get(pk=txn.portfolio_id)
    if not portfolio.cash_aware_enabled:
        return
    specs = _stock_settlement_specs(txn)
    _sync_settlement_specs(txn, portfolio, specs)


def sync_mutual_fund_settlement(
    txn: Transaction, detail: MutualFundTransactionDetail
) -> None:
    portfolio = Portfolio.objects.get(pk=txn.portfolio_id)
    if not portfolio.cash_aware_enabled:
        return
    specs = _mf_settlement_specs(txn, detail)
    _sync_settlement_specs(txn, portfolio, specs)


def delete_linked_settlement_before_transaction(txn: Transaction) -> None:
    portfolio = Portfolio.objects.get(pk=txn.portfolio_id)
    if not portfolio.cash_aware_enabled:
        return
    linked = list(
        CashLedgerEntry.objects.filter(linked_transaction_id=txn.pk).order_by("id")
    )
    if not linked:
        return
    assert_delete_entries_would_not_make_cash_negative(linked)
    for entry in linked:
        entry.delete()


@db_transaction.atomic
def save_transaction_with_stock_settlement(txn: Transaction) -> Transaction:
    """Persist stock transaction and sync settlement when cash-aware."""
    portfolio = Portfolio.objects.select_for_update().get(pk=txn.portfolio_id)
    txn.save()
    if portfolio.cash_aware_enabled:
        sync_stock_settlement(txn)
    return txn
