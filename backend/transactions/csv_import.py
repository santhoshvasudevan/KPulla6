"""Parse and validate transaction CSV for bulk import (all-or-nothing)."""
from __future__ import annotations

import csv
import io
import math
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from math import gcd
from typing import Any

from transactions.models import TransactionType
from transactions.services import (
    TransactionValidationError,
    normalize_asset_symbol,
    validate_transaction_payload,
)

REQUIRED_HEADER_KEYS = frozenset(
    {"action", "date", "asset symbol", "qty", "price/share"}
)


def _norm_header(h: str) -> str:
    return (h or "").strip().lower()


def parse_money(value: str) -> tuple[Decimal, str]:
    if value is None:
        raise ValueError("empty price")
    s = str(value).strip().strip('"').replace("\u00a0", " ")
    currency = "EUR"
    if "€" in s:
        currency = "EUR"
    s = s.replace("€", "").strip()
    if s.upper().endswith("EUR"):
        s = s[:-3].strip()
    s = s.replace(",", "")
    if not s:
        raise ValueError("empty price")
    return Decimal(s), currency


def parse_plain_decimal(value: str) -> Decimal:
    s = (value or "").strip().strip('"').replace(",", "")
    if not s:
        raise ValueError("empty value")
    return Decimal(s)


def parse_date_mmddyy(s: str) -> date:
    s = (s or "").strip()
    if not s:
        raise ValueError("empty date")
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError("Date must be MM/DD/YY")


def map_action(raw: str) -> str | None:
    x = (raw or "").strip().upper()
    if x == "BUY":
        return TransactionType.BUY
    if x == "SELL":
        return TransactionType.SELL
    if x == "DIVIDEND":
        return TransactionType.DIVIDEND
    if x == "SWAP":
        return "SWAP"
    if x == "STOCK_SPLIT":
        return TransactionType.STOCK_SPLIT
    return None


def _swap_ratio(q1: Decimal, q2: Decimal) -> tuple[Decimal, Decimal]:
    if q1 == 0 or q2 == 0:
        raise ValueError("SWAP quantities must be non-zero")
    if (q1 > 0 and q2 > 0) or (q1 < 0 and q2 < 0):
        raise ValueError("SWAP pair requires one negative and one positive quantity")
    a = int(round(abs(q1)))
    b = int(round(abs(q2)))
    if abs(q1 - round(q1)) > Decimal("1e-6") or abs(q2 - round(q2)) > Decimal("1e-6"):
        raise ValueError("SWAP quantities must be whole numbers")
    if a <= 0 or b <= 0:
        raise ValueError("Invalid SWAP quantities")
    g = gcd(a, b)
    return Decimal(a // g), Decimal(b // g)


def _validate_payload(data: dict[str, Any], row: int, errors: list[dict[str, Any]]) -> bool:
    try:
        validate_transaction_payload(
            txn_type=data["type"],
            asset_symbol=data.get("asset_symbol"),
            date=data.get("date"),
            quantity=data.get("quantity"),
            price_per_share=data.get("price_per_share"),
            fees=data.get("fees"),
            currency=data.get("currency"),
            split_from=data.get("split_from"),
            split_to=data.get("split_to"),
        )
        return True
    except TransactionValidationError as exc:
        message = str(exc)
        field = "row"
        if "split_from" in message or "split_to" in message:
            field = "split_from" if "split_from" in message else "split_to"
        elif "quantity" in message:
            field = "Qty"
        elif "price_per_share" in message:
            field = "Price/Share"
        elif "asset_symbol" in message:
            field = "ASSET SYMBOL"
        elif "date" in message:
            field = "Date"
        errors.append({"row": row, "field": field, "message": message})
        return False


def parse_transaction_csv(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    buf = io.StringIO(text)
    reader = csv.reader(buf)
    rows = list(reader)
    if not rows:
        return [], [{"row": 1, "field": "file", "message": "Empty CSV"}]

    headers_norm = [_norm_header(h) for h in rows[0]]
    header_set = set(headers_norm)
    missing = sorted(REQUIRED_HEADER_KEYS - header_set)
    if missing:
        return [], [
            {
                "row": 1,
                "field": "headers",
                "message": f"Missing required columns: {', '.join(missing)}",
            }
        ]

    col = {h: i for i, h in enumerate(headers_norm)}
    has_fees = "fees" in col

    normal_payloads: list[tuple[int, dict[str, Any]]] = []
    direct_splits: list[tuple[int, dict[str, Any]]] = []
    pending_swaps: dict[tuple[date, str], list[dict[str, Any]]] = defaultdict(list)

    for line_no, vals in enumerate(rows[1:], start=2):
        while len(vals) < len(headers_norm):
            vals.append("")
        action_raw = vals[col["action"]].strip()
        date_raw = vals[col["date"]].strip()
        sym_raw = vals[col["asset symbol"]].strip()
        qty_raw = vals[col["qty"]].strip()
        price_raw = vals[col["price/share"]]
        fees_raw = vals[col["fees"]].strip() if has_fees else ""

        txn_type = map_action(action_raw)
        if txn_type is None:
            errors.append(
                {"row": line_no, "field": "Action", "message": f"Invalid action: {action_raw!r}"}
            )
            continue

        try:
            d = parse_date_mmddyy(date_raw)
        except ValueError as e:
            errors.append({"row": line_no, "field": "Date", "message": str(e)})
            continue

        if not normalize_asset_symbol(sym_raw):
            errors.append(
                {
                    "row": line_no,
                    "field": "ASSET SYMBOL",
                    "message": "Asset symbol must not be empty",
                }
            )
            continue

        fees_val = Decimal("0")
        if fees_raw != "":
            try:
                fees_val = Decimal(fees_raw.replace(",", ""))
            except InvalidOperation:
                errors.append({"row": line_no, "field": "FEES", "message": "Invalid fees"})
                continue
            if fees_val < 0:
                errors.append({"row": line_no, "field": "FEES", "message": "fees must be >= 0"})
                continue

        if txn_type == "SWAP":
            if not (qty_raw or "").strip():
                errors.append(
                    {"row": line_no, "field": "Qty", "message": "Quantity is required"}
                )
                continue
            try:
                qty_val = Decimal(qty_raw.replace(",", ""))
            except InvalidOperation:
                errors.append({"row": line_no, "field": "Qty", "message": "Invalid quantity"})
                continue
            if not qty_val.is_finite():
                errors.append(
                    {
                        "row": line_no,
                        "field": "Qty",
                        "message": "Quantity must be a finite number",
                    }
                )
                continue
            try:
                price_val, cur = parse_money(price_raw)
            except (ValueError, InvalidOperation) as e:
                errors.append(
                    {"row": line_no, "field": "Price/Share", "message": f"Invalid price: {e!s}"}
                )
                continue
            pending_swaps[(d, normalize_asset_symbol(sym_raw))].append(
                {
                    "row": line_no,
                    "qty": qty_val,
                    "fees": fees_val,
                    "currency": cur,
                }
            )
            continue

        if txn_type == TransactionType.STOCK_SPLIT:
            if not (qty_raw or "").strip():
                errors.append(
                    {"row": line_no, "field": "split_from", "message": "split_from is required"}
                )
                continue
            if not (str(price_raw) or "").strip():
                errors.append(
                    {"row": line_no, "field": "split_to", "message": "split_to is required"}
                )
                continue
            try:
                split_from = parse_plain_decimal(qty_raw)
            except (ValueError, InvalidOperation):
                errors.append(
                    {"row": line_no, "field": "split_from", "message": "Invalid split_from"}
                )
                continue
            try:
                split_to = parse_plain_decimal(str(price_raw))
            except (ValueError, InvalidOperation):
                errors.append(
                    {"row": line_no, "field": "split_to", "message": "Invalid split_to"}
                )
                continue
            if split_from <= 0:
                errors.append(
                    {
                        "row": line_no,
                        "field": "split_from",
                        "message": "split_from must be greater than 0",
                    }
                )
                continue
            if split_to <= 0:
                errors.append(
                    {
                        "row": line_no,
                        "field": "split_to",
                        "message": "split_to must be greater than 0",
                    }
                )
                continue
            payload = {
                "asset_symbol": normalize_asset_symbol(sym_raw),
                "date": d,
                "type": TransactionType.STOCK_SPLIT,
                "quantity": Decimal("0"),
                "price_per_share": Decimal("0"),
                "currency": "EUR",
                "fees": fees_val,
                "split_from": split_from,
                "split_to": split_to,
            }
            if not _validate_payload(payload, line_no, errors):
                continue
            direct_splits.append((line_no, payload))
            continue

        try:
            price_val, cur = parse_money(price_raw)
        except (ValueError, InvalidOperation) as e:
            errors.append(
                {"row": line_no, "field": "Price/Share", "message": f"Invalid price: {e!s}"}
            )
            continue

        if not (qty_raw or "").strip():
            errors.append({"row": line_no, "field": "Qty", "message": "Quantity is required"})
            continue
        try:
            qty_val = Decimal(qty_raw.replace(",", ""))
        except InvalidOperation:
            errors.append({"row": line_no, "field": "Qty", "message": "Invalid quantity"})
            continue
        if not qty_val.is_finite():
            errors.append(
                {
                    "row": line_no,
                    "field": "Qty",
                    "message": "Quantity must be a finite number",
                }
            )
            continue

        if qty_val <= 0:
            errors.append(
                {"row": line_no, "field": "Qty", "message": "Quantity must be positive"}
            )
            continue
        if price_val < 0:
            errors.append(
                {
                    "row": line_no,
                    "field": "Price/Share",
                    "message": "price_per_share must be greater than or equal to 0",
                }
            )
            continue

        payload = {
            "asset_symbol": normalize_asset_symbol(sym_raw),
            "date": d,
            "type": txn_type,
            "quantity": qty_val,
            "price_per_share": price_val,
            "currency": cur,
            "fees": fees_val,
        }
        if not _validate_payload(payload, line_no, errors):
            continue
        normal_payloads.append((line_no, payload))

    split_payloads: list[tuple[int, dict[str, Any]]] = []
    for key, legs in pending_swaps.items():
        d, sym = key
        if len(legs) != 2:
            for leg in legs:
                errors.append(
                    {
                        "row": leg["row"],
                        "field": "Action",
                        "message": (
                            "SWAP requires exactly two rows with the same date and asset symbol"
                        ),
                    }
                )
            continue
        a, b = legs[0], legs[1]
        try:
            sf, st = _swap_ratio(a["qty"], b["qty"])
        except ValueError as e:
            r = min(a["row"], b["row"])
            errors.append({"row": r, "field": "Qty", "message": str(e)})
            continue
        line_no = min(a["row"], b["row"])
        currency = a["currency"]
        payload = {
            "asset_symbol": sym,
            "date": d,
            "type": TransactionType.STOCK_SPLIT,
            "quantity": Decimal("0"),
            "price_per_share": Decimal("0"),
            "currency": currency,
            "fees": a["fees"] + b["fees"],
            "split_from": sf,
            "split_to": st,
        }
        if not _validate_payload(payload, line_no, errors):
            continue
        split_payloads.append((line_no, payload))

    if errors:
        return [], errors

    merged = normal_payloads + direct_splits + split_payloads
    merged.sort(key=lambda x: x[0])
    return [p for _, p in merged], []
