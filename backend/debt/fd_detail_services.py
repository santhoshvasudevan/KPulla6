"""Fixed deposit detail page aggregation (ORM + pure finance)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from debt.fd_maturity_services import resolve_maturity_display
from debt.interest_payment_services import list_fixed_deposit_interest_payments
from debt.models import FixedDeposit, FixedDepositInterestPayment
from debt.services import get_fixed_deposit
from finance.fd_interest_schedule import (
    ExpectedScheduleRow,
    build_detailed_calculation,
    date_in_range,
    financial_years_for_range,
    format_indian_financial_year,
    generate_expected_interest_schedule,
    match_payment_to_schedule_row,
    parse_indian_financial_year,
    schedule_row_status,
)


class FdDetailValidationError(Exception):
    pass


@dataclass(frozen=True)
class FinancialYearFilter:
    label: str | None
    fy_start: date | None
    fy_end: date | None


def _parse_fy_filter(
    *,
    financial_year: str | None,
    fy_start: date | None,
    fy_end: date | None,
) -> FinancialYearFilter:
    if financial_year:
        start, end = parse_indian_financial_year(financial_year)
        return FinancialYearFilter(label=financial_year, fy_start=start, fy_end=end)
    if fy_start and fy_end:
        if fy_end < fy_start:
            raise FdDetailValidationError("fy_end must be on or after fy_start.")
        return FinancialYearFilter(
            label=format_indian_financial_year(fy_start),
            fy_start=fy_start,
            fy_end=fy_end,
        )
    return FinancialYearFilter(label=None, fy_start=None, fy_end=None)


def _decimal_sum(values: list[Decimal]) -> Decimal:
    total = Decimal("0")
    for value in values:
        total += Decimal(value)
    return total


def _decimal_to_json(value: Decimal) -> float:
    return float(value)


def _payment_summary(payments: list[FixedDepositInterestPayment]) -> dict[str, Decimal]:
    active = [p for p in payments if not p.is_reversed]
    gross = _decimal_sum([p.gross_interest for p in active])
    tax = _decimal_sum([p.tax_withheld for p in active])
    net = _decimal_sum([p.net_interest for p in active])
    return {
        "actual_gross_interest": gross,
        "tax_withheld": tax,
        "actual_net_interest": net,
    }


def _schedule_summary(rows: list[ExpectedScheduleRow]) -> dict[str, Decimal]:
    return {
        "expected_gross_interest": _decimal_sum(
            [row.expected_gross_interest for row in rows]
        ),
    }


def _fy_summary(
    *,
    schedule_rows: list[ExpectedScheduleRow],
    payments: list[FixedDepositInterestPayment],
    fy_filter: FinancialYearFilter,
) -> dict[str, Any] | None:
    if fy_filter.fy_start is None or fy_filter.fy_end is None:
        return None

    expected_fy = _decimal_sum(
        [
            row.expected_gross_interest
            for row in schedule_rows
            if date_in_range(row.expected_payout_date, fy_filter.fy_start, fy_filter.fy_end)
        ]
    )
    active = [p for p in payments if not p.is_reversed]
    actual_fy_payments = [
        p
        for p in active
        if date_in_range(p.payment_date, fy_filter.fy_start, fy_filter.fy_end)
    ]
    gross_fy = _decimal_sum([p.gross_interest for p in actual_fy_payments])
    tax_fy = _decimal_sum([p.tax_withheld for p in actual_fy_payments])
    net_fy = _decimal_sum([p.net_interest for p in actual_fy_payments])

    return {
        "financial_year": fy_filter.label,
        "fy_start": fy_filter.fy_start.isoformat(),
        "fy_end": fy_filter.fy_end.isoformat(),
        "expected_gross_interest_fy": _decimal_to_json(expected_fy),
        "actual_gross_interest_fy": _decimal_to_json(gross_fy),
        "tax_withheld_fy": _decimal_to_json(tax_fy),
        "actual_net_interest_fy": _decimal_to_json(net_fy),
        "variance_actual_vs_expected_fy": _decimal_to_json(gross_fy - expected_fy),
    }


def _available_financial_years(
    fd: FixedDeposit,
    payments: list[FixedDepositInterestPayment],
) -> list[str]:
    dates = [fd.investment_date, fd.maturity_date]
    for payment in payments:
        if not payment.is_reversed:
            dates.append(payment.payment_date)
    return financial_years_for_range(min(dates), max(dates))


def _serialize_schedule_row(
    row: ExpectedScheduleRow,
    *,
    matched_payment: FixedDepositInterestPayment | None,
    as_of_date: date,
) -> dict[str, Any]:
    status = schedule_row_status(row, matched_payment=matched_payment, as_of_date=as_of_date)
    payload: dict[str, Any] = {
        "period_index": row.period_index,
        "period_start_date": row.period_start_date.isoformat(),
        "period_end_date": row.period_end_date.isoformat(),
        "expected_payout_date": row.expected_payout_date.isoformat(),
        "days_in_period": row.days_in_period,
        "expected_gross_interest": float(row.expected_gross_interest),
        "is_partial_period": row.is_partial_period,
        "schedule_row_type": row.schedule_row_type,
        "status": status,
        "matched_payment_id": matched_payment.id if matched_payment else None,
    }
    if matched_payment:
        payload["matched_payment"] = {
            "id": matched_payment.id,
            "payment_date": matched_payment.payment_date.isoformat(),
            "gross_interest": float(matched_payment.gross_interest),
            "tax_withheld": float(matched_payment.tax_withheld),
            "net_interest": float(matched_payment.net_interest),
            "bank_account_id": matched_payment.bank_account_id,
            "bank_account_name": matched_payment.bank_account.name,
            "is_reversed": matched_payment.is_reversed,
            "comment": matched_payment.comment,
        }
    else:
        payload["matched_payment"] = None
    return payload


def _serialize_detailed_calculation(fd: FixedDeposit) -> dict[str, Any]:
    calc = build_detailed_calculation(fd)
    return {
        "principal": float(calc.principal),
        "interest_rate_percent": float(calc.interest_rate_percent),
        "investment_date": calc.investment_date.isoformat(),
        "maturity_date": calc.maturity_date.isoformat(),
        "tenure_days": calc.tenure_days,
        "tenure_years_fractional": float(calc.tenure_years_fractional),
        "payout_frequency": calc.payout_frequency,
        "day_count_method": calc.day_count_method,
        "period_generation_basis": calc.period_generation_basis,
        "expected_periodic_interest": (
            float(calc.expected_periodic_interest)
            if calc.expected_periodic_interest is not None
            else None
        ),
        "expected_total_interest": (
            float(calc.expected_total_interest)
            if calc.expected_total_interest is not None
            else None
        ),
        "expected_maturity_value": (
            float(calc.expected_maturity_value)
            if calc.expected_maturity_value is not None
            else None
        ),
        "approximation_note": calc.approximation_note,
    }


def build_fixed_deposit_detail(
    user: AbstractBaseUser,
    fd_id: int,
    *,
    financial_year: str | None = None,
    fy_start: date | None = None,
    fy_end: date | None = None,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    fd = get_fixed_deposit(user, fd_id)
    payments = list_fixed_deposit_interest_payments(user, fd_id)
    fy_filter = _parse_fy_filter(
        financial_year=financial_year,
        fy_start=fy_start,
        fy_end=fy_end,
    )
    as_of = as_of_date or date.today()

    schedule_rows = generate_expected_interest_schedule(fd)
    matched_ids: set[int] = set()
    serialized_schedule: list[dict[str, Any]] = []
    for row in schedule_rows:
        matched = match_payment_to_schedule_row(row, payments, already_matched_ids=matched_ids)
        if matched:
            matched_ids.add(matched.id)
        serialized_schedule.append(
            _serialize_schedule_row(row, matched_payment=matched, as_of_date=as_of)
        )

    estimate = resolve_maturity_display(fd)
    term_schedule = _schedule_summary(schedule_rows)
    term_actual = _payment_summary(payments)
    warnings: list[str] = []
    if estimate.get("maturity_value_warning"):
        warnings.append(estimate["maturity_value_warning"])
    if estimate.get("estimate_message"):
        warnings.append(estimate["estimate_message"])

    return {
        "fixed_deposit_id": fd.id,
        "estimate_summary": estimate,
        "expected_interest_schedule": serialized_schedule,
        "actual_interest_payments": [
            {
                "id": p.id,
                "payment_date": p.payment_date.isoformat(),
                "gross_interest": float(p.gross_interest),
                "tax_withheld": float(p.tax_withheld),
                "net_interest": float(p.net_interest),
                "bank_account_id": p.bank_account_id,
                "bank_account_name": p.bank_account.name,
                "cash_movement_id": p.cash_movement_id,
                "comment": p.comment,
                "is_reversed": p.is_reversed,
                "reversed_at": p.reversed_at.isoformat() if p.reversed_at else None,
            }
            for p in payments
        ],
        "financial_year_options": _available_financial_years(fd, payments),
        "financial_year_summary": _fy_summary(
            schedule_rows=schedule_rows,
            payments=payments,
            fy_filter=fy_filter,
        ),
        "term_totals": {
            "expected_gross_interest": _decimal_to_json(term_schedule["expected_gross_interest"]),
            "actual_gross_interest": _decimal_to_json(term_actual["actual_gross_interest"]),
            "tax_withheld": _decimal_to_json(term_actual["tax_withheld"]),
            "actual_net_interest": _decimal_to_json(term_actual["actual_net_interest"]),
            "variance_actual_vs_expected": _decimal_to_json(
                term_actual["actual_gross_interest"] - term_schedule["expected_gross_interest"]
            ),
        },
        "detailed_calculation": _serialize_detailed_calculation(fd),
        "warnings": warnings,
    }
