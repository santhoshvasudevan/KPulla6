"""Cash-aware BUY/SELL settlement ledger rows linked to asset transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_CASH_AMOUNT_QUANT = Decimal("0.0001")

from django.db import transaction as db_transaction

from cash.models import CashEntryType, CashLedgerEntry
from cash.services import (
    assert_delete_settlement_would_not_make_cash_negative,
    assert_sufficient_cash_for_purchase,
    validate_cash_currency,
)
from finance.cash import (
    mf_buy_cash_required,
    mf_sell_cash_proceeds,
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


def _stock_settlement_spec(txn: Transaction) -> SettlementSpec:
    if txn.type in {TransactionType.STOCK_SPLIT, TransactionType.DIVIDEND}:
        return SettlementSpec(None, None, None, None, "")

    currency = validate_cash_currency(txn.currency)
    note = _settlement_note(txn)

    if txn.type == TransactionType.BUY:
        required = stock_buy_cash_required(
            txn.quantity, txn.price_per_share or Decimal("0"), txn.fees
        )
        return SettlementSpec(
            CashEntryType.BUY_SETTLEMENT,
            -_quantize_cash_amount(required),
            txn.date,
            currency,
            note,
        )

    if txn.type == TransactionType.SELL:
        proceeds = stock_sell_cash_proceeds(
            txn.quantity, txn.price_per_share or Decimal("0"), txn.fees
        )
        if proceeds <= 0:
            raise _validation_error(
                "SELL proceeds must be greater than zero after fees"
            )
        return SettlementSpec(
            CashEntryType.SELL_SETTLEMENT,
            _quantize_cash_amount(proceeds),
            txn.date,
            currency,
            note,
        )

    return SettlementSpec(None, None, None, None, "")


def _mf_settlement_spec(
    txn: Transaction, detail: MutualFundTransactionDetail
) -> SettlementSpec:
    currency = validate_cash_currency(txn.currency)
    note = _settlement_note(txn)
    ledger_date = detail.investment_date

    if txn.type == TransactionType.BUY:
        required = mf_buy_cash_required(detail.paid_value)
        return SettlementSpec(
            CashEntryType.BUY_SETTLEMENT,
            -_quantize_cash_amount(required),
            ledger_date,
            currency,
            note,
        )

    if txn.type == TransactionType.SELL:
        proceeds = mf_sell_cash_proceeds(
            paid_value=detail.paid_value,
            units_allotted=detail.units_allotted,
            nav=detail.nav,
            fees=txn.fees,
        )
        if proceeds <= 0:
            raise _validation_error("SELL proceeds must be greater than zero")
        return SettlementSpec(
            CashEntryType.SELL_SETTLEMENT,
            _quantize_cash_amount(proceeds),
            ledger_date,
            currency,
            note,
        )

    return SettlementSpec(None, None, None, None, "")


def _get_linked_settlement(txn: Transaction) -> CashLedgerEntry | None:
    return (
        CashLedgerEntry.objects.filter(linked_transaction_id=txn.pk)
        .order_by("id")
        .first()
    )


def _apply_settlement_spec(
    txn: Transaction,
    portfolio: Portfolio,
    spec: SettlementSpec,
    existing: CashLedgerEntry | None,
) -> None:
    if spec.entry_type is None:
        if existing is not None:
            if existing.entry_type == CashEntryType.SELL_SETTLEMENT:
                assert_delete_settlement_would_not_make_cash_negative(existing)
            existing.delete()
        return

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


def sync_stock_settlement(txn: Transaction) -> None:
    portfolio = Portfolio.objects.get(pk=txn.portfolio_id)
    if not portfolio.cash_aware_enabled:
        return
    existing = _get_linked_settlement(txn)
    spec = _stock_settlement_spec(txn)
    _apply_settlement_spec(txn, portfolio, spec, existing)


def sync_mutual_fund_settlement(
    txn: Transaction, detail: MutualFundTransactionDetail
) -> None:
    portfolio = Portfolio.objects.get(pk=txn.portfolio_id)
    if not portfolio.cash_aware_enabled:
        return
    existing = _get_linked_settlement(txn)
    spec = _mf_settlement_spec(txn, detail)
    _apply_settlement_spec(txn, portfolio, spec, existing)


def delete_linked_settlement_before_transaction(txn: Transaction) -> None:
    portfolio = Portfolio.objects.get(pk=txn.portfolio_id)
    if not portfolio.cash_aware_enabled:
        return
    existing = _get_linked_settlement(txn)
    if existing is None:
        return
    if existing.entry_type == CashEntryType.SELL_SETTLEMENT:
        assert_delete_settlement_would_not_make_cash_negative(existing)
    existing.delete()


@db_transaction.atomic
def save_transaction_with_stock_settlement(txn: Transaction) -> Transaction:
    """Persist stock transaction and sync settlement when cash-aware."""
    portfolio = Portfolio.objects.select_for_update().get(pk=txn.portfolio_id)
    txn.save()
    if portfolio.cash_aware_enabled:
        sync_stock_settlement(txn)
    return txn
