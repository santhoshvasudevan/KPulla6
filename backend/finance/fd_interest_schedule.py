"""Pure FD expected interest schedule and Indian financial-year helpers."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

from finance.fixed_deposits import (
    PAYOUT_PERIODS_PER_YEAR,
    estimate_fd_interest,
    is_compounded_fd,
    is_payout_fd,
)

_ZERO = Decimal("0")
_DAYS_PER_YEAR = Decimal("365")
_CURRENCY_QUANT = Decimal("0.0001")

FREQUENCY_MONTHS = {
    "MONTHLY": 1,
    "QUARTERLY": 3,
    "HALF_YEARLY": 6,
    "ANNUALLY": 12,
}

SCHEDULE_ROW_PAYOUT = "PAYOUT"
SCHEDULE_ROW_MATURITY_ACCRUAL = "MATURITY_ACCRUAL"

SCHEDULE_STATUS_RECORDED = "RECORDED"
SCHEDULE_STATUS_OVERDUE = "OVERDUE"
SCHEDULE_STATUS_UPCOMING = "UPCOMING"
SCHEDULE_STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"


class FixedDepositScheduleLike(Protocol):
    principal_amount: Decimal
    interest_rate_percent: Decimal
    interest_payout_frequency: str
    investment_date: date
    maturity_date: date


class InterestPaymentLike(Protocol):
    id: int
    payment_date: date
    gross_interest: Decimal
    tax_withheld: Decimal
    net_interest: Decimal
    is_reversed: bool


@dataclass(frozen=True)
class ExpectedScheduleRow:
    period_index: int
    period_start_date: date
    period_end_date: date
    expected_payout_date: date
    days_in_period: int
    expected_gross_interest: Decimal
    is_partial_period: bool
    schedule_row_type: str


@dataclass(frozen=True)
class DetailedCalculation:
    principal: Decimal
    interest_rate_percent: Decimal
    investment_date: date
    maturity_date: date
    tenure_days: int
    tenure_years_fractional: Decimal
    payout_frequency: str
    day_count_method: str
    period_generation_basis: str
    expected_periodic_interest: Decimal | None
    expected_total_interest: Decimal | None
    expected_maturity_value: Decimal | None
    approximation_note: str


def _quantize_currency(value: Decimal) -> Decimal:
    return value.quantize(_CURRENCY_QUANT, rounding=ROUND_HALF_UP)


def add_calendar_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _days_between(start: date, end: date) -> int:
    return (end - start).days


def _interest_for_days(principal: Decimal, rate_percent: Decimal, days: int) -> Decimal:
    if days <= 0 or rate_percent <= 0:
        return _ZERO
    rate = rate_percent / Decimal("100")
    return _quantize_currency(principal * rate * Decimal(days) / _DAYS_PER_YEAR)


def _full_period_interest(
    principal: Decimal,
    rate_percent: Decimal,
    payout_frequency: str,
) -> Decimal:
    periods_per_year = PAYOUT_PERIODS_PER_YEAR[payout_frequency]
    rate = rate_percent / Decimal("100")
    return _quantize_currency(principal * rate / Decimal(periods_per_year))


def generate_payout_schedule(fd: FixedDepositScheduleLike) -> list[ExpectedScheduleRow]:
    """Generate expected payout dates and gross interest per period (Actual/365 partials)."""
    if not is_payout_fd(fd):
        return []

    principal = Decimal(fd.principal_amount)
    inv = fd.investment_date
    mat = fd.maturity_date
    if not inv or not mat or mat <= inv or principal <= 0:
        return []

    freq = fd.interest_payout_frequency
    interval_months = FREQUENCY_MONTHS[freq]
    rows: list[ExpectedScheduleRow] = []
    period_start = inv
    period_index = 0

    while period_start < mat:
        period_index += 1
        scheduled_end = add_calendar_months(inv, period_index * interval_months)
        period_end = scheduled_end if scheduled_end < mat else mat
        days = _days_between(period_start, period_end)
        if days <= 0:
            break

        is_partial = period_end == mat and scheduled_end > mat
        if is_partial:
            expected_interest = _interest_for_days(
                principal, Decimal(fd.interest_rate_percent), days
            )
        else:
            expected_interest = _full_period_interest(
                principal, Decimal(fd.interest_rate_percent), freq
            )

        rows.append(
            ExpectedScheduleRow(
                period_index=period_index,
                period_start_date=period_start,
                period_end_date=period_end,
                expected_payout_date=period_end,
                days_in_period=days,
                expected_gross_interest=expected_interest,
                is_partial_period=is_partial,
                schedule_row_type=SCHEDULE_ROW_PAYOUT,
            )
        )
        if period_end >= mat:
            break
        period_start = period_end

    return rows


def generate_compounded_maturity_row(fd: FixedDepositScheduleLike) -> list[ExpectedScheduleRow]:
    """Single maturity accrual row for compounded FDs."""
    if not is_compounded_fd(fd):
        return []

    inv = fd.investment_date
    mat = fd.maturity_date
    if not inv or not mat or mat <= inv:
        return []

    estimate = estimate_fd_interest(fd)
    days = _days_between(inv, mat)
    total_interest = estimate.total_interest or _ZERO

    return [
        ExpectedScheduleRow(
            period_index=1,
            period_start_date=inv,
            period_end_date=mat,
            expected_payout_date=mat,
            days_in_period=days,
            expected_gross_interest=total_interest,
            is_partial_period=False,
            schedule_row_type=SCHEDULE_ROW_MATURITY_ACCRUAL,
        )
    ]


def generate_expected_interest_schedule(fd: FixedDepositScheduleLike) -> list[ExpectedScheduleRow]:
    if is_compounded_fd(fd):
        return generate_compounded_maturity_row(fd)
    if is_payout_fd(fd):
        return generate_payout_schedule(fd)
    return []


def parse_indian_financial_year(label: str) -> tuple[date, date]:
    """Parse FY label like 2025-26 into April–March bounds."""
    parts = label.strip().split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid financial year label: {label}")
    start_year = int(parts[0])
    end_suffix = parts[1]
    if len(end_suffix) == 2:
        end_year = (start_year // 100) * 100 + int(end_suffix)
        if end_year < start_year:
            end_year += 100
    else:
        end_year = int(end_suffix)
    return date(start_year, 4, 1), date(end_year, 3, 31)


def format_indian_financial_year(fy_start: date) -> str:
    end_year = fy_start.year + 1
    return f"{fy_start.year}-{str(end_year)[-2:]}"


def financial_years_for_range(min_date: date, max_date: date) -> list[str]:
    if min_date > max_date:
        return []
    start = date(min_date.year if min_date.month >= 4 else min_date.year - 1, 4, 1)
    end = date(max_date.year if max_date.month >= 4 else max_date.year - 1, 4, 1)
    labels: list[str] = []
    cursor = start
    while cursor <= end:
        labels.append(format_indian_financial_year(cursor))
        cursor = date(cursor.year + 1, 4, 1)
    return labels


def date_in_range(d: date, start: date, end: date) -> bool:
    return start <= d <= end


def build_detailed_calculation(fd: FixedDepositScheduleLike) -> DetailedCalculation:
    estimate = estimate_fd_interest(fd)
    inv = fd.investment_date
    mat = fd.maturity_date
    days = _days_between(inv, mat) if inv and mat else 0
    years = Decimal(days) / _DAYS_PER_YEAR if days > 0 else _ZERO

    if is_compounded_fd(fd):
        basis = "Single maturity accrual row at maturity date; annual compounding Actual/365."
    elif is_payout_fd(fd):
        basis = (
            "Payout dates on investment-date calendar anniversaries by frequency; "
            "full periods use rate/periods-per-year; final partial uses Actual/365."
        )
    else:
        basis = "Unsupported payout frequency."

    return DetailedCalculation(
        principal=Decimal(fd.principal_amount),
        interest_rate_percent=Decimal(fd.interest_rate_percent),
        investment_date=inv,
        maturity_date=mat,
        tenure_days=days,
        tenure_years_fractional=years,
        payout_frequency=fd.interest_payout_frequency,
        day_count_method="Actual/365",
        period_generation_basis=basis,
        expected_periodic_interest=estimate.periodic_interest,
        expected_total_interest=estimate.total_interest,
        expected_maturity_value=estimate.maturity_value,
        approximation_note=(
            "This is an estimate. Banks may use different day-count, rounding, "
            "compounding, tax withholding, or premature closure rules. "
            "Final settlement and credited interest are recorded separately."
        ),
    )


def schedule_row_status(
    row: ExpectedScheduleRow,
    *,
    matched_payment: InterestPaymentLike | None,
    as_of_date: date,
) -> str:
    if row.schedule_row_type == SCHEDULE_ROW_MATURITY_ACCRUAL:
        return SCHEDULE_STATUS_NOT_APPLICABLE
    if matched_payment is not None:
        return SCHEDULE_STATUS_RECORDED
    if row.expected_payout_date < as_of_date:
        return SCHEDULE_STATUS_OVERDUE
    return SCHEDULE_STATUS_UPCOMING


def match_payment_to_schedule_row(
    row: ExpectedScheduleRow,
    payments: list[InterestPaymentLike],
    *,
    already_matched_ids: set[int],
) -> InterestPaymentLike | None:
    active = [p for p in payments if not p.is_reversed and p.id not in already_matched_ids]

    for payment in active:
        if date_in_range(payment.payment_date, row.period_start_date, row.period_end_date):
            return payment

    best: InterestPaymentLike | None = None
    best_delta = 46
    for payment in active:
        delta = abs((payment.payment_date - row.expected_payout_date).days)
        if delta <= 45 and delta < best_delta:
            best = payment
            best_delta = delta
    return best
