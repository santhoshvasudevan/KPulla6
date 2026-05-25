from datetime import date, timedelta
from decimal import Decimal

import pytest

from finance.fifo import calculate_fifo_cost_basis_metrics
from finance.oversell import detect_oversell
from finance.splits import apply_stock_split_adjustments
from finance.twror import compute_twror_series
from finance.types import Transaction, TransactionType
from finance.xirr import build_xirr_cashflows, calculate_xirr


def _buy(d: date, qty, px, *, sym: str = "A", fees=0) -> Transaction:
    return Transaction(
        type=TransactionType.BUY,
        date=d,
        quantity=Decimal(str(qty)),
        price=Decimal(str(px)),
        fees=Decimal(str(fees)),
        asset_symbol=sym,
    )


def _sell(d: date, qty, px, *, sym: str = "A", fees=0) -> Transaction:
    return Transaction(
        type=TransactionType.SELL,
        date=d,
        quantity=Decimal(str(qty)),
        price=Decimal(str(px)),
        fees=Decimal(str(fees)),
        asset_symbol=sym,
    )


def _split(d: date, sf, st, *, sym: str = "A") -> Transaction:
    return Transaction(
        type=TransactionType.STOCK_SPLIT,
        date=d,
        quantity=Decimal("0"),
        price=Decimal("0"),
        fees=Decimal("0"),
        asset_symbol=sym,
        split_from=Decimal(str(sf)),
        split_to=Decimal(str(st)),
    )


def test_buy_adds_cumulative_quantity_and_invested_amount():
    m = calculate_fifo_cost_basis_metrics(
        [_buy(date(2026, 1, 1), 10, 150)],
        current_price=Decimal("160"),
    )
    assert m.cumulative_qty == Decimal("10")
    assert m.cumulative_invested_amount == Decimal("1500")


def test_sell_reduces_quantity():
    m = calculate_fifo_cost_basis_metrics(
        [
            _buy(date(2026, 1, 1), 10, 150),
            _sell(date(2026, 2, 1), 4, 160),
        ],
        current_price=Decimal("160"),
    )
    assert m.cumulative_qty == Decimal("6")


def test_sell_depletes_earliest_lots_fifo():
    m = calculate_fifo_cost_basis_metrics(
        [
            _buy(date(2026, 1, 1), 10, 100),
            _buy(date(2026, 1, 2), 5, 120),
            _sell(date(2026, 1, 3), 8, 130),
        ],
        current_price=Decimal("130"),
    )
    assert m.cumulative_qty == Decimal("7")
    assert m.cumulative_invested_amount == Decimal("800")
    assert m.realized_pl == Decimal("240")


def test_realized_pl_profitable_sell():
    m = calculate_fifo_cost_basis_metrics(
        [
            _buy(date(2026, 1, 1), 10, 100),
            _sell(date(2026, 2, 1), 4, 150),
        ],
        current_price=Decimal("150"),
    )
    assert m.realized_pl == Decimal("200")


def test_realized_pl_loss_sell():
    m = calculate_fifo_cost_basis_metrics(
        [
            _buy(date(2026, 1, 1), 10, 100),
            _sell(date(2026, 2, 1), 10, 90),
        ],
        current_price=Decimal("100"),
    )
    assert m.realized_pl == Decimal("-100")


def test_partial_sell_leaves_remaining_cost_basis():
    m = calculate_fifo_cost_basis_metrics(
        [
            _buy(date(2026, 1, 1), 10, 100),
            _sell(date(2026, 2, 1), 4, 150),
        ],
        current_price=Decimal("150"),
    )
    assert m.cumulative_qty == Decimal("6")
    assert m.cumulative_invested_amount == Decimal("600")
    assert m.avg_cost_per_share == Decimal("100")


def test_avg_cost_is_invested_over_qty():
    m = calculate_fifo_cost_basis_metrics(
        [
            _buy(date(2026, 1, 1), 10, 100),
            _buy(date(2026, 1, 2), 5, 120),
        ],
        current_price=Decimal("120"),
    )
    assert m.avg_cost_per_share == Decimal("1600") / Decimal("15")


def test_unrealized_pl_uses_current_price():
    m = calculate_fifo_cost_basis_metrics(
        [_buy(date(2026, 1, 1), 10, 100)],
        current_price=Decimal("120"),
    )
    assert m.unrealized_pl == Decimal("200")


def test_multiple_transactions_final_metrics():
    today = date.today()
    d1 = today - timedelta(days=5)
    d2 = today - timedelta(days=4)
    d3 = today - timedelta(days=3)
    d4 = today - timedelta(days=2)
    d5 = today - timedelta(days=1)
    txns = [
        _buy(d1, 10, 100),
        _buy(d2, 5, 120),
        _sell(d3, 8, 130),
        _buy(d4, 10, 125),
        _sell(d5, 17, 130),
    ]
    m = calculate_fifo_cost_basis_metrics(txns, current_price=Decimal("130"))
    assert m.cumulative_qty == Decimal("0")
    assert m.realized_pl == Decimal("400")
    assert m.unrealized_pl == Decimal("0")


def test_oversell_matches_kpulla5_fifo_behavior():
    m = calculate_fifo_cost_basis_metrics(
        [
            _buy(date(2026, 1, 1), 10, 100),
            _sell(date(2026, 2, 1), 15, 110),
        ],
        current_price=Decimal("100"),
    )
    assert m.cumulative_qty == Decimal("0")
    assert m.cumulative_invested_amount == Decimal("0")
    assert m.realized_pl == Decimal("650")


def test_oversell_respects_stock_split_before_sell():
    txns = [
        _buy(date(2022, 11, 11), 10, 100, sym="ANET"),
        _split(date(2024, 12, 3), 1, 4, sym="ANET"),
        _sell(date(2026, 2, 6), 20, 110, sym="ANET"),
    ]
    assert detect_oversell(txns) is False


def test_oversell_true_when_sell_exceeds_split_adjusted_qty():
    txns = [
        _buy(date(2022, 11, 11), 10, 100, sym="ANET"),
        _split(date(2024, 12, 3), 1, 4, sym="ANET"),
        _sell(date(2026, 2, 6), 50, 110, sym="ANET"),
    ]
    assert detect_oversell(txns) is True


def test_empty_transaction_list_safe_zeros():
    m = calculate_fifo_cost_basis_metrics([], current_price=Decimal("100"))
    assert m.cumulative_qty == Decimal("0")
    assert m.cumulative_invested_amount == Decimal("0")
    assert m.realized_pl == Decimal("0")
    assert m.unrealized_pl == Decimal("0")


def test_fully_sold_asset_zero_qty_and_realized_pl():
    m = calculate_fifo_cost_basis_metrics(
        [
            _buy(date(2026, 1, 1), 10, 100),
            _sell(date(2026, 2, 1), 10, 90),
        ],
        current_price=Decimal("100"),
    )
    assert m.cumulative_qty == Decimal("0")
    assert m.realized_pl == Decimal("-100")
    assert m.unrealized_pl == Decimal("0")


def test_stock_split_adjusts_prior_same_symbol_transactions():
    txns = [
        _buy(date(2023, 12, 1), 1, 200, sym="AAPL"),
        _split(date(2024, 1, 1), 1, 20, sym="AAPL"),
    ]
    adjusted = apply_stock_split_adjustments(txns)
    assert len(adjusted) == 1
    assert adjusted[0].quantity == Decimal("20")
    assert adjusted[0].price == Decimal("10")


def test_stock_split_does_not_adjust_after_split_date():
    txns = [
        _split(date(2024, 1, 1), 1, 20, sym="AAPL"),
        _buy(date(2024, 1, 2), 1, 200, sym="AAPL"),
    ]
    adjusted = apply_stock_split_adjustments(txns)
    assert len(adjusted) == 1
    assert adjusted[0].quantity == Decimal("1")
    assert adjusted[0].price == Decimal("200")


def test_stock_split_does_not_adjust_different_symbols():
    txns = [
        _buy(date(2023, 12, 1), 10, 100, sym="MSFT"),
        _buy(date(2023, 12, 1), 1, 200, sym="AAPL"),
        _split(date(2024, 1, 1), 1, 20, sym="AAPL"),
    ]
    by_sym = {t.asset_symbol: t for t in apply_stock_split_adjustments(txns)}
    assert by_sym["MSFT"].quantity == Decimal("10")
    assert by_sym["AAPL"].quantity == Decimal("20")


def test_stock_split_rows_not_in_adjusted_buy_sell_list():
    txns = [
        _buy(date(2023, 12, 1), 1, 200, sym="AAPL"),
        _split(date(2024, 1, 1), 1, 20, sym="AAPL"),
    ]
    adjusted = apply_stock_split_adjustments(txns)
    assert all(t.type != TransactionType.STOCK_SPLIT for t in adjusted)


def test_invalid_split_values_ignored():
    txns = [
        _buy(date(2023, 12, 1), 1, 200, sym="AAPL"),
        Transaction(
            type=TransactionType.STOCK_SPLIT,
            date=date(2024, 1, 1),
            quantity=Decimal("0"),
            price=Decimal("0"),
            fees=Decimal("0"),
            asset_symbol="AAPL",
            split_from=Decimal("0"),
            split_to=Decimal("20"),
        ),
    ]
    adjusted = apply_stock_split_adjustments(txns)
    assert adjusted[0].quantity == Decimal("1")
    assert adjusted[0].price == Decimal("200")


def test_xirr_buy_negative_sell_positive_terminal_value():
    txns = [_buy(date(2025, 1, 1), 100, 1)]
    dates, amounts = build_xirr_cashflows(
        txns, current_price=Decimal("1.1"), current_date=date(2026, 1, 1)
    )
    assert amounts[0] < 0
    xirr = calculate_xirr(
        txns, current_price=Decimal("1.1"), current_date=date(2026, 1, 1)
    )
    assert xirr is not None
    assert round(xirr, 2) == 0.10


def test_xirr_sell_positive_cash_flow():
    txns = [
        _buy(date(2025, 1, 1), 100, 1),
        _sell(date(2025, 7, 2), 50, 1.2),
    ]
    dates, amounts = build_xirr_cashflows(
        txns, current_price=Decimal("1.2"), current_date=date(2026, 1, 1)
    )
    assert any(a > 0 for a in amounts[1:])
    xirr = calculate_xirr(
        txns, current_price=Decimal("1.2"), current_date=date(2026, 1, 1)
    )
    assert xirr is not None
    assert xirr > 0


def test_xirr_terminal_holding_value_included():
    txns = [_buy(date(2025, 1, 1), 10, 100)]
    xirr = calculate_xirr(
        txns, current_price=Decimal("50"), current_date=date(2026, 1, 1)
    )
    assert xirr is not None
    assert xirr < 0


def test_twror_chain_link_basic():
    series = [
        {"date": "2026-01-01", "portfolio_value": 100},
        {"date": "2026-01-02", "portfolio_value": 110},
    ]
    points = compute_twror_series(series, flows_by_date={})
    assert points[0].value is None
    assert points[1].value is not None
    assert abs(points[1].value - Decimal("10")) < Decimal("0.0001")


def test_twror_ignores_flow_in_return():
    series = [
        {"date": "2026-01-01", "portfolio_value": 100},
        {"date": "2026-01-02", "portfolio_value": 200},
    ]
    flows = {date(2026, 1, 2): Decimal("100")}
    points = compute_twror_series(series, flows_by_date=flows)
    assert points[1].value is not None
    assert abs(points[1].value - Decimal("0")) < Decimal("0.0001")


def test_twror_handles_zero_beginning_value():
    series = [
        {"date": "2026-01-01", "portfolio_value": 0},
        {"date": "2026-01-02", "portfolio_value": 100},
    ]
    points = compute_twror_series(series, flows_by_date={})
    assert points[1].value is None
