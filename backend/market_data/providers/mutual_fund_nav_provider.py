from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable, Protocol

from market_data.providers.amfi_nav_parser import (
    filter_nav_rows_by_range,
    mfapi_status_ok,
    normalize_api_scheme_code,
    parse_mfapi_latest_nav,
    parse_mfapi_nav_entries,
)

logger = logging.getLogger(__name__)

DEFAULT_MFAPI_BASE_URL = "https://api.mfapi.in"
DEFAULT_NAV_FETCH_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class NavPoint:
    date: date
    nav: Decimal
    currency: str = "INR"


class MutualFundNavProvider(Protocol):
    def get_latest_nav(self, scheme_code: str) -> NavPoint | None:
        """Return the provider's latest NAV for scheme_code, or None if unavailable."""

    def get_nav_history(
        self, scheme_code: str, start: date, end: date
    ) -> list[NavPoint]:
        """Return daily NAV rows for scheme_code in [start, end] inclusive."""


class AmfiNavFetchError(Exception):
    """Network or parse failure fetching NAV data from MFAPI."""


HttpGetJson = Callable[[str, float], dict]


def http_get_json(url: str, timeout: float = DEFAULT_NAV_FETCH_TIMEOUT_SECONDS) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "KPulla6/1.0 (mutual-fund-nav-sync)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise AmfiNavFetchError(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise AmfiNavFetchError(f"Network error for {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AmfiNavFetchError(f"Timeout fetching {url}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AmfiNavFetchError(f"Invalid JSON from {url}") from exc

    if not isinstance(payload, dict):
        raise AmfiNavFetchError(f"Expected JSON object from {url}")
    return payload


class AmfiNavProvider:
    """
    Live AMFI-sourced NAV provider via MFAPI (https://api.mfapi.in).

    Used only in explicit sync paths (management commands, POST /nav/refresh,
    sync_market_data). Read APIs use cached HistoricalPrice rows only.

    Inject ``http_get`` in tests to avoid network calls.
    """

    source_label = "amfi"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_MFAPI_BASE_URL,
        timeout: float = DEFAULT_NAV_FETCH_TIMEOUT_SECONDS,
        http_get: HttpGetJson | None = None,
    ):
        self._base_url = (base_url or DEFAULT_MFAPI_BASE_URL).rstrip("/")
        self._timeout = timeout
        self._http_get = http_get or http_get_json
        self.category_responses = {}

    def _scheme_url(self, scheme_code: str, *, latest: bool = False) -> str | None:
        code = normalize_api_scheme_code(scheme_code)
        if not code:
            logger.warning("Invalid mutual fund scheme_code for NAV fetch: %r", scheme_code)
            return None
        suffix = "/latest" if latest else ""
        return f"{self._base_url}/mf/{code}{suffix}"

    def _history_url(self, scheme_code: str, start: date, end: date) -> str | None:
        code = normalize_api_scheme_code(scheme_code)
        if not code:
            logger.warning("Invalid mutual fund scheme_code for NAV history: %r", scheme_code)
            return None
        return (
            f"{self._base_url}/mf/{code}"
            f"?startDate={start.isoformat()}&endDate={end.isoformat()}"
        )

    @staticmethod
    def _category_metadata(payload, scheme_code):
        meta = payload.get("meta") if isinstance(payload, dict) and mfapi_status_ok(payload) else None
        if not isinstance(meta, dict) or normalize_api_scheme_code(str(meta.get("scheme_code"))) != normalize_api_scheme_code(scheme_code):
            return None
        return meta

    def get_category_metadata(self, scheme_code):
        url = self._scheme_url(scheme_code, latest=True)
        return self._category_metadata(self._http_get(url, self._timeout), scheme_code) if url else None

    def get_latest_nav(self, scheme_code: str) -> NavPoint | None:
        url = self._scheme_url(scheme_code, latest=True)
        if not url:
            return None
        try:
            payload = self._http_get(url, self._timeout)
        except AmfiNavFetchError as exc:
            logger.error("Failed to fetch latest NAV for %s: %s", scheme_code, exc)
            return None
        point = parse_mfapi_latest_nav(payload)
        if point is None:
            logger.warning("No latest NAV data in MFAPI response for scheme %s", scheme_code)
            return None
        return NavPoint(date=point[0], nav=point[1], currency="INR")

    def get_nav_history(self, scheme_code: str, start: date, end: date) -> list[NavPoint]:
        if start > end:
            return []
        url = self._history_url(scheme_code, start, end)
        if not url:
            return []
        try:
            payload = self._http_get(url, self._timeout)
        except AmfiNavFetchError as exc:
            logger.error(
                "Failed to fetch NAV history for %s (%s..%s): %s",
                scheme_code,
                start,
                end,
                exc,
            )
            raise
        if (
            not isinstance(payload, dict)
            or not mfapi_status_ok(payload)
            or not isinstance(payload.get("data"), list)
        ):
            raise AmfiNavFetchError(f"Invalid NAV history response for scheme {scheme_code}")
        meta = payload.get("meta")
        if isinstance(meta, dict) and meta.get("scheme_code") is not None and not self._category_metadata(payload, scheme_code):
            raise AmfiNavFetchError(f"MFAPI returned a different scheme for {scheme_code}")
        rows = parse_mfapi_nav_entries(payload)
        if payload["data"] and not rows:
            raise AmfiNavFetchError(f"No valid NAV history rows for scheme {scheme_code}")
        self.category_responses[scheme_code] = self._category_metadata(payload, scheme_code)
        if not rows:
            logger.info(
                "Empty NAV history in MFAPI response for scheme %s (%s..%s)",
                scheme_code,
                start,
                end,
            )
            return []
        filtered = filter_nav_rows_by_range(rows, start, end)
        return [
            NavPoint(date=row_date, nav=nav, currency="INR")
            for row_date, nav in filtered
        ]


def default_mutual_fund_nav_provider() -> MutualFundNavProvider:
    return AmfiNavProvider()
