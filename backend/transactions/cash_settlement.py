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
    assert_proposed_ledger_non_negative,
    assert_sufficient_cash_for_purchase,
    validate_cash_currency,
)
from finance.cash import (
    CashLedgerPoint,
    dividend_net_cash,
    mf_buy_cash_required,
    mf_sell_cash_proceeds,
    sell_tax_released_amount,
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


def mf_sell_settlement_preview(
    *,
    paid_value: Decimal,
    units_allotted: Decimal,
    nav: Decimal,
    fees: Decimal,
    actual_cash_received: Decimal | None,
) -> dict[str, Decimal] | None:
    """Calculated MF SELL proceeds and tax gap as settlement would record them; None when not positive."""
    proceeds = mf_sell_cash_proceeds(
        paid_value=paid_value, units_allotted=units_allotted, nav=nav, fees=fees
    )
    if proceeds <= 0:
        return None
    calculated = _quantize_cash_amount(proceeds)
    return {
        "calculated_proceeds": calculated,
        "tax_withheld": _quantize_cash_amount(
            sell_tax_withheld_amount(calculated, actual_cash_received)
        ),
        "tax_released": _quantize_cash_amount(
            sell_tax_released_amount(calculated, actual_cash_received)
        ),
    }


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
    released = sell_tax_released_amount(calculated_proceeds, txn.actual_cash_received)
    if released > 0:
        specs.append(
            SettlementSpec(
                CashEntryType.TAX_RELEASED,
                _quantize_cash_amount(released),
                ledger_date,
                currency,
                _tax_withheld_note(txn),
            )
        )
    return specs


def _dividend_settlement_specs(txn: Transaction) -> list[SettlementSpec]:
    if txn.dividend_gross is None:
        return []
    gross = _quantize_cash_amount(txn.dividend_gross)
    tax = _quantize_cash_amount(txn.dividend_tax_withheld or Decimal("0"))
    if gross <= 0:
        raise _validation_error("Gross dividend must be greater than 0")
    if tax < 0 or tax > gross:
        raise _validation_error("Tax withheld cannot exceed gross dividend")
    if dividend_net_cash(gross, tax) < 0:
        raise _validation_error("Tax withheld cannot exceed gross dividend")

    currency = validate_cash_currency(txn.currency)
    note = _settlement_note(txn)
    specs = [
        SettlementSpec(
            CashEntryType.DIVIDEND_CASH,
            gross,
            txn.date,
            currency,
            note,
        )
    ]
    if tax > 0:
        specs.append(
            SettlementSpec(
                CashEntryType.TAX,
                -tax,
                txn.date,
                currency,
                _tax_withheld_note(txn) or note,
            )
        )
    return specs


def _assert_dividend_replacement_non_negative(
    txn: Transaction,
    portfolio: Portfolio,
    specs: list[SettlementSpec],
) -> None:
    existing = list(
        CashLedgerEntry.objects.filter(linked_transaction_id=txn.pk).order_by("id")
    )
    if not existing:
        return
    currency = specs[0].currency if specs else existing[0].currency
    dates = [entry.date for entry in existing]
    dates.extend(spec.ledger_date for spec in specs if spec.ledger_date is not None)
    proposed = [
        CashLedgerPoint(
            date=spec.ledger_date,
            currency=spec.currency or currency,
            amount=spec.amount,
        )
        for spec in specs
        if spec.ledger_date is not None and spec.amount is not None and spec.currency
    ]
    assert_proposed_ledger_non_negative(
        portfolio,
        currency,
        exclude_entry_ids={entry.id for entry in existing},
        proposed_points=proposed,
        from_date=min(dates),
    )


def _stock_settlement_specs(txn: Transaction) -> list[SettlementSpec]:
    if txn.type == TransactionType.STOCK_SPLIT:
        return []
    if txn.type == TransactionType.DIVIDEND:
        return _dividend_settlement_specs(txn)

    currency = validate_cash_currency(txn.currency)
    note = _settlement_note(txn)

    if txn.type == TransactionType.BUY:
        required = _quantize_cash_amount(
            stock_buy_cash_required(
                txn.quantity, txn.price_per_share or Decimal("0"), txn.fees
            )
        )
        # Zero-cost receipts (spin-off, bonus, demerger) move no cash.
        if required == 0:
            return []
        return [
            SettlementSpec(
                CashEntryType.BUY_SETTLEMENT,
                -required,
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
    """Primary linked BUY/SELL settlement row (excludes tax withheld/released)."""
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
        if entry.entry_type
        in (
            CashEntryType.SELL_SETTLEMENT,
            CashEntryType.TAX_RELEASED,
            CashEntryType.DIVIDEND_CASH,
        )
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
    if txn.type == TransactionType.DIVIDEND:
        _assert_dividend_replacement_non_negative(txn, portfolio, specs)
    _sync_settlement_specs(txn, portfolio, specs)


def _linked_entry_snapshot(txn: Transaction) -> list[tuple]:
    return list(
        CashLedgerEntry.objects.filter(linked_transaction_id=txn.pk)
        .order_by("id")
        .values_list("portfolio_id", "currency", "date", "entry_type", "amount")
    )


def _assert_changed_settlements_non_negative(
    before: list[tuple], after: list[tuple]
) -> None:
    """Reject a settlement replacement that drives any affected later balance negative."""
    if sorted(before) == sorted(after):
        return
    earliest: dict[tuple[int, str], date] = {}
    for portfolio_id, currency, entry_date, _type, _amount in [*before, *after]:
        key = (portfolio_id, currency)
        earliest[key] = min(entry_date, earliest.get(key, entry_date))
    for (portfolio_id, currency), from_date in earliest.items():
        assert_proposed_ledger_non_negative(
            Portfolio.objects.get(pk=portfolio_id),
            currency,
            exclude_entry_ids=set(),
            proposed_points=[],
            from_date=from_date,
        )


def sync_mutual_fund_settlement(
    txn: Transaction, detail: MutualFundTransactionDetail
) -> None:
    portfolio = Portfolio.objects.get(pk=txn.portfolio_id)
    if not portfolio.cash_aware_enabled:
        return
    specs = _mf_settlement_specs(txn, detail)
    before = _linked_entry_snapshot(txn)
    _sync_settlement_specs(txn, portfolio, specs)
    if before:
        _assert_changed_settlements_non_negative(before, _linked_entry_snapshot(txn))


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
