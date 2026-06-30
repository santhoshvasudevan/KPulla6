"""CSV export for FD interest & tax report (FD-TAX-2)."""

from __future__ import annotations

import csv
import io
from datetime import date

from debt.interest_report_service import (
    SOURCE_LABELS,
    FixedDepositInterestReportResult,
)

CSV_COLUMNS = [
    "Date",
    "Source Type",
    "Source Label",
    "Portfolio",
    "Bank / Institution",
    "Bank Account",
    "FD Account",
    "Currency",
    "Gross Interest",
    "Tax Withheld",
    "Net Interest",
    "Display Currency",
    "Gross Interest Display",
    "Tax Withheld Display",
    "Net Interest Display",
    "Comment",
]


def interest_report_csv_filename(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> str:
    if start_date and end_date:
        return f"fd-interest-tax-{start_date.isoformat()}-to-{end_date.isoformat()}.csv"
    if start_date:
        return f"fd-interest-tax-from-{start_date.isoformat()}.csv"
    if end_date:
        return f"fd-interest-tax-to-{end_date.isoformat()}.csv"
    return "fd-interest-tax-all.csv"


def _csv_cell(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    return str(value)


def build_interest_report_csv(result: FixedDepositInterestReportResult) -> str:
    """Return UTF-8 CSV text (detail rows only; no footer totals)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for row in result.rows:
        source_type = row.get("source_type", "")
        writer.writerow(
            [
                row.get("date", ""),
                source_type,
                SOURCE_LABELS.get(source_type, source_type),
                row.get("portfolio_name", ""),
                row.get("institution_name", ""),
                row.get("bank_account_name", ""),
                row.get("deposit_account_number", ""),
                row.get("currency", ""),
                _csv_cell(row.get("gross_interest")),
                _csv_cell(row.get("tax_withheld")),
                _csv_cell(row.get("net_interest")),
                _csv_cell(row.get("display_currency")),
                _csv_cell(row.get("gross_interest_display")),
                _csv_cell(row.get("tax_withheld_display")),
                _csv_cell(row.get("net_interest_display")),
                row.get("comment", "") or "",
            ]
        )
    return buffer.getvalue()
