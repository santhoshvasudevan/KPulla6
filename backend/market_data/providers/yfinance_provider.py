from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from market_data.providers.base import DailyPrice, PriceProvider
from market_data.price_lookup import normalize_asset_symbol

logger = logging.getLogger(__name__)


def _norm_ccy(value: str | None) -> str:
    return (value or "USD").strip().upper() or "USD"


def _adj_close_or_close_series(hist):
    if hist is None or getattr(hist, "empty", True):
        return None
    if "Adj Close" in hist.columns:
        return hist["Adj Close"]
    if "Close" in hist.columns:
        return hist["Close"]
    return None


def _finite_decimal_from_provider_value(value) -> Decimal | None:
    try:
        as_float = float(value)
    except (TypeError, ValueError, InvalidOperation):
        return None
    if not math.isfinite(as_float):
        return None

    decimal_value = Decimal(str(as_float))
    if not decimal_value.is_finite():
        return None
    return decimal_value


class YFinancePriceProvider:
    """yfinance-backed price history (used by sync commands and manual refresh only)."""

    def __init__(self, *, adjust_close: bool = True):
        # Benchmarks keep adjusted closes. Stocks use the market close
        # (split-adjusted, not dividend-adjusted) so dividends are explicit.
        self.adjust_close = adjust_close

    def fetch_history(
        self, symbol: str, start: date, end: date
    ) -> tuple[list[DailyPrice], str | None]:
        import yfinance as yf

        sym = (symbol or "").strip()
        if not sym:
            return [], None

        ticker = yf.Ticker(sym)
        hist = ticker.history(
            start=start,
            end=end + timedelta(days=1),
            auto_adjust=self.adjust_close,
        )
        if self.adjust_close:
            series = _adj_close_or_close_series(hist)
        elif hist is None or getattr(hist, "empty", True) or "Close" not in hist.columns:
            series = None
        else:
            series = hist["Close"]
        if series is None or series.empty:
            return [], None

        currency: str | None = None
        try:
            info_ccy = ticker.info.get("currency")
            if info_ccy:
                currency = _norm_ccy(str(info_ccy))
        except Exception:
            logger.debug("Could not read ticker currency for %s", sym, exc_info=True)

        rows: list[DailyPrice] = []
        for idx, val in series.items():
            close = _finite_decimal_from_provider_value(val)
            if close is None:
                logger.warning(
                    "Skipping invalid yfinance price for %s on %s: %r",
                    sym,
                    idx,
                    val,
                )
                continue
            row_date = idx.date() if hasattr(idx, "date") else idx
            rows.append(
                DailyPrice(
                    date=row_date,
                    close=close,
                    currency=currency or "USD",
                )
            )
        return rows, currency


def default_price_provider() -> PriceProvider:
    """Adjusted closes for benchmarks."""
    return YFinancePriceProvider(adjust_close=True)


def default_stock_price_provider() -> PriceProvider:
    """Market close for stocks: split-adjusted, not dividend-adjusted."""
    return YFinancePriceProvider(adjust_close=False)


def normalize_provider_symbol(symbol: str, *, is_benchmark: bool = False) -> str:
    """Uppercase stock tickers; preserve benchmark caret symbols."""
    sym = (symbol or "").strip()
    if not sym:
        return ""
    if is_benchmark:
        return sym.upper()
    return normalize_asset_symbol(sym)
