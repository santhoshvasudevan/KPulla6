from datetime import date
from decimal import Decimal

from finance.cash import (
    CashLedgerPoint,
    cash_balance_by_currency,
    cash_balance_on_date,
    cash_balance_timeseries,
    cash_shortfall,
    has_sufficient_cash,
    mf_buy_cash_required,
    mf_sell_cash_proceeds,
    stock_buy_cash_required,
    stock_sell_cash_proceeds,
)


def _pt(d: str, currency: str, amount: str) -> CashLedgerPoint:
    return CashLedgerPoint(
        date=date.fromisoformat(d),
        currency=currency,
        amount=Decimal(amount),
    )


def test_stock_buy_and_sell_settlement_amounts():
    assert stock_buy_cash_required(Decimal("10"), Decimal("100"), Decimal("5")) == Decimal(
        "1005"
    )
    assert stock_sell_cash_proceeds(Decimal("10"), Decimal("100"), Decimal("5")) == Decimal(
        "995"
    )


def test_mf_buy_and_sell_settlement_amounts():
    assert mf_buy_cash_required(Decimal("4255")) == Decimal("4255")
    assert mf_sell_cash_proceeds(
        paid_value=Decimal("5000"),
        units_allotted=Decimal("100"),
        nav=Decimal("42.5"),
        fees=Decimal("5"),
    ) == Decimal("5000")
    assert mf_sell_cash_proceeds(
        paid_value=Decimal("0"),
        units_allotted=Decimal("100"),
        nav=Decimal("42.5"),
        fees=Decimal("5"),
    ) == Decimal("4245")


def test_cash_balance_by_currency():
    entries = [
        _pt("2026-01-01", "EUR", "1000"),
        _pt("2026-01-02", "EUR", "-200"),
        _pt("2026-01-01", "USD", "500"),
    ]
    assert cash_balance_by_currency(entries) == {
        "EUR": Decimal("800"),
        "USD": Decimal("500"),
    }


def test_cash_balance_on_date():
    entries = [
        _pt("2026-01-01", "EUR", "1000"),
        _pt("2026-01-10", "EUR", "-300"),
        _pt("2026-01-05", "USD", "100"),
    ]
    assert cash_balance_on_date(entries, date(2026, 1, 4)) == {
        "EUR": Decimal("1000"),
    }
    assert cash_balance_on_date(entries, date(2026, 1, 15)) == {
        "EUR": Decimal("700"),
        "USD": Decimal("100"),
    }


def test_multi_currency_balances_stay_separate():
    entries = [
        _pt("2026-01-01", "EUR", "100"),
        _pt("2026-01-01", "INR", "5000"),
    ]
    balances = cash_balance_by_currency(entries)
    assert balances["EUR"] == Decimal("100")
    assert balances["INR"] == Decimal("5000")
    assert "EUR" not in balances or balances.get("USD") is None


def test_has_sufficient_cash_and_shortfall():
    entries = [
        _pt("2026-01-01", "EUR", "1000"),
        _pt("2026-01-05", "EUR", "-400"),
    ]
    as_of = date(2026, 1, 10)
    assert has_sufficient_cash(entries, "EUR", Decimal("600"), as_of)
    assert not has_sufficient_cash(entries, "EUR", Decimal("601"), as_of)
    assert cash_shortfall(entries, "EUR", Decimal("601"), as_of) == Decimal("1")
    assert cash_shortfall(entries, "EUR", Decimal("600"), as_of) == Decimal("0")


def test_negative_adjustment():
    entries = [
        _pt("2026-01-01", "EUR", "100"),
        _pt("2026-01-02", "EUR", "-30"),
    ]
    assert cash_balance_by_currency(entries)["EUR"] == Decimal("70")


def test_cash_balance_timeseries_carries_forward():
    entries = [
        _pt("2026-01-01", "EUR", "1000"),
        _pt("2026-01-03", "EUR", "-100"),
    ]
    series = cash_balance_timeseries(
        entries, date(2026, 1, 1), date(2026, 1, 4)
    )
    assert series["EUR"] == [
        (date(2026, 1, 1), Decimal("1000")),
        (date(2026, 1, 2), Decimal("1000")),
        (date(2026, 1, 3), Decimal("900")),
        (date(2026, 1, 4), Decimal("900")),
    ]


def test_cash_balance_timeseries_includes_pre_start_opening():
    entries = [
        _pt("2025-12-31", "EUR", "500"),
        _pt("2026-01-02", "EUR", "100"),
    ]
    series = cash_balance_timeseries(
        entries, date(2026, 1, 1), date(2026, 1, 2)
    )
    assert series["EUR"][0] == (date(2026, 1, 1), Decimal("500"))
    assert series["EUR"][1] == (date(2026, 1, 2), Decimal("600"))
