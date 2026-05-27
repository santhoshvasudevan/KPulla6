"""Parse MFAPI (AMFI-sourced) JSON — no network I/O."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MFAPI_DATE_FORMATS = ("%d-%m-%Y", "%Y-%m-%d")
NavRow = tuple[date, Decimal]


def normalize_api_scheme_code(scheme_code: str) -> str | None:
    code = (scheme_code or "").strip()
    if not code or not code.isdigit():
        return None
    return code


def parse_mfapi_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in MFAPI_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_mfapi_nav_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        nav = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if nav <= 0:
        return None
    return nav


def mfapi_status_ok(payload: dict) -> bool:
    return str(payload.get("status", "")).upper() == "SUCCESS"


def parse_mfapi_nav_entries(payload: dict) -> list[NavRow]:
    if not isinstance(payload, dict) or not mfapi_status_ok(payload):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    rows: list[NavRow] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        row_date = parse_mfapi_date(str(entry.get("date", "")))
        nav = parse_mfapi_nav_decimal(entry.get("nav"))
        if row_date is None or nav is None:
            continue
        rows.append((row_date, nav))
    return rows


def filter_nav_rows_by_range(rows: list[NavRow], start: date, end: date) -> list[NavRow]:
    return [r for r in rows if start <= r[0] <= end]


def parse_mfapi_latest_nav(payload: dict) -> NavRow | None:
    rows = parse_mfapi_nav_entries(payload)
    if not rows:
        return None
    return max(rows, key=lambda r: r[0])
