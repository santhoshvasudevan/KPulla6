"""Framework-independent finance logic (no Django imports)."""

from finance.fifo import (
    FifoCostBasisMetrics,
    build_split_adjusted_lot_snapshots,
    calculate_fifo_cost_basis_metrics,
)
from finance.oversell import detect_oversell
from finance.splits import apply_stock_split_adjustments
from finance.twror import TwrorPoint, compute_twror_series
from finance.types import Transaction, TransactionType
from finance.xirr import build_xirr_cashflows, calculate_xirr

__all__ = [
    "FifoCostBasisMetrics",
    "Transaction",
    "TransactionType",
    "TwrorPoint",
    "apply_stock_split_adjustments",
    "build_split_adjusted_lot_snapshots",
    "detect_oversell",
    "build_xirr_cashflows",
    "calculate_fifo_cost_basis_metrics",
    "calculate_xirr",
    "compute_twror_series",
]
