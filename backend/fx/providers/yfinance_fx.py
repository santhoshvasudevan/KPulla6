from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from fx.providers.base import DailyFxRate, FxProvider

logger = logging.getLogger(__name__)


def _norm_ccy(value: str | None) -> str:
    return (value or "").strip().upper()


def resolve_fx_rate(
    from_currency: str, to_currency: str, ticker_symbol: str, close_rate: float
) -> Decimal:
    pair = (ticker_symbol or "").upper().replace("=X", "")
    frm = _norm_ccy(from_currency)
    to = _norm_ccy(to_currency)
    if pair == f"{frm}{to}":
        return Decimal(str(close_rate))
    if pair == f"{to}{frm}":
        if float(close_rate) == 0:
            raise ValueError("Invalid zero FX close rate")
        return Decimal(str(1.0 / float(close_rate)))
    raise ValueError(f"Unable to resolve FX pair direction for {ticker_symbol}")


class YFinanceFxProvider:
    def fetch_rates(
        self, from_currency: str, to_currency: str, start: date, end: date
    ) -> list[DailyFxRate]:
        import yfinance as yf

        frm = _norm_ccy(from_currency)
        to = _norm_ccy(to_currency)
        if not frm or not to or frm == to or start > end:
            return []

        candidates = [f"{frm}{to}=X", f"{to}{frm}=X"]
        history = None
        used_ticker = None
        for ticker_symbol in candidates:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(start=start, end=end + timedelta(days=1))
            if hist is not None and not hist.empty:
                history = hist
                used_ticker = ticker_symbol
                break

        if history is None or history.empty or not used_ticker:
            logger.warning(
                "FX history unavailable for %s -> %s (%s to %s)",
                frm,
                to,
                start,
                end,
            )
            return []

        rows: list[DailyFxRate] = []
        for idx, row in history.iterrows():
            row_date = idx.date() if hasattr(idx, "date") else idx
            rate = resolve_fx_rate(frm, to, used_ticker, float(row["Close"]))
            rows.append(DailyFxRate(date=row_date, rate=rate))
        return rows


def default_fx_provider() -> FxProvider:
    return YFinanceFxProvider()
