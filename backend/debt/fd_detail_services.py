"""Fixed deposit detail page aggregation (ORM + pure finance)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from debt.fd_maturity_services import resolve_maturity_display
from debt.interest_payment_services import list_fixed_deposit_interest_payments
from debt.models import (
    FixedDeposit,
    FixedDepositInterestPayment,
    FixedDepositPendingPayout,
    FixedDepositPendingPayoutStatus,
    FixedDepositRenewalGroup,
    FixedDepositSettlement,
)
from debt.serializers import pending_payout_summary
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
from finance.fd_renewal_allocation import allocate_renewal_proceeds


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


def _maturity_interest_for_term(fd: FixedDeposit) -> dict[str, Any]:
    """
    Confirmed maturity/renewal interest on the originating term.

    Renewal + linked settlement count once (prefer the renewal group).
    Pending estimates are excluded; confirmed delayed payouts are handled separately.
    """
    renewal = (
        FixedDepositRenewalGroup.objects.filter(old_fixed_deposit=fd)
        .order_by("id")
        .first()
    )
    if renewal is not None:
        gross = Decimal(renewal.gross_interest)
        tax = Decimal(renewal.tax_withheld)
        net = Decimal(renewal.net_interest)
        event_date = renewal.renewal_date
        try:
            allocation = allocate_renewal_proceeds(
                old_principal=Decimal(renewal.old_principal),
                net_interest=net,
                new_principal=Decimal(renewal.direct_reinvest_amount),
                cash_payout_amount=Decimal(renewal.cash_payout_amount),
            )
            interest_cash = allocation.interest_cash_amount
            reinvested = allocation.reinvested_interest_amount
        except ValueError:
            interest_cash = None
            reinvested = None
        return {
            "gross": gross,
            "tax": tax,
            "net": net,
            "event_date": event_date,
            "interest_cash_amount": interest_cash,
            "reinvested_interest_amount": reinvested,
            "source": "RENEWAL",
        }

    settlement = (
        FixedDepositSettlement.objects.filter(fixed_deposit=fd).order_by("id").first()
    )
    if settlement is not None:
        gross = Decimal(settlement.gross_interest)
        tax = Decimal(settlement.tax_withheld)
        net = Decimal(settlement.net_interest)
        return {
            "gross": gross,
            "tax": tax,
            "net": net,
            "event_date": settlement.settlement_date,
            # Settle pays all final interest to the bank (none reinvested).
            "interest_cash_amount": net,
            "reinvested_interest_amount": Decimal("0"),
            "source": "SETTLEMENT",
        }

    return {
        "gross": Decimal("0"),
        "tax": Decimal("0"),
        "net": Decimal("0"),
        "event_date": None,
        "interest_cash_amount": Decimal("0"),
        "reinvested_interest_amount": Decimal("0"),
        "source": None,
    }


def _optional_decimal_json(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _payment_summary(
    payments: list[FixedDepositInterestPayment],
    confirmed_payout: FixedDepositPendingPayout | None = None,
    maturity_interest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active = [p for p in payments if not p.is_reversed]
    gross = _decimal_sum([p.gross_interest for p in active])
    tax = _decimal_sum([p.tax_withheld for p in active])
    net = _decimal_sum([p.net_interest for p in active])
    # Periodic interest payments are always bank credits.
    interest_cash = _decimal_sum([p.net_interest for p in active])
    reinvested = Decimal("0")
    split_known = True

    if confirmed_payout is not None:
        gross += confirmed_payout.gross_interest
        tax += confirmed_payout.tax_withheld
        net += confirmed_payout.net_interest
        interest_cash += confirmed_payout.net_interest

    maturity = maturity_interest or {}
    if maturity.get("source"):
        gross += Decimal(maturity["gross"])
        tax += Decimal(maturity["tax"])
        net += Decimal(maturity["net"])
        cash_part = maturity.get("interest_cash_amount")
        reinvest_part = maturity.get("reinvested_interest_amount")
        if cash_part is None or reinvest_part is None:
            # Legacy renewal: cannot complete term-level paid/reinvested totals.
            split_known = False
        else:
            interest_cash += Decimal(cash_part)
            reinvested += Decimal(reinvest_part)

    return {
        "actual_gross_interest": gross,
        "tax_withheld": tax,
        "actual_net_interest": net,
        # Null means the maturity split is unknown — do not report a partial
        # cash total that would look complete next to Unavailable reinvested.
        "interest_cash_amount": interest_cash if split_known else None,
        "reinvested_interest_amount": reinvested if split_known else None,
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
    confirmed_payout: FixedDepositPendingPayout | None = None,
    maturity_interest: dict[str, Any] | None = None,
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
    interest_cash_fy = _decimal_sum([p.net_interest for p in actual_fy_payments])
    reinvested_fy = Decimal("0")
    split_known = True

    if confirmed_payout is not None and date_in_range(
        confirmed_payout.payment_date, fy_filter.fy_start, fy_filter.fy_end
    ):
        gross_fy += confirmed_payout.gross_interest
        tax_fy += confirmed_payout.tax_withheld
        net_fy += confirmed_payout.net_interest
        interest_cash_fy += confirmed_payout.net_interest

    maturity = maturity_interest or {}
    event_date = maturity.get("event_date")
    if maturity.get("source") and event_date is not None and date_in_range(
        event_date, fy_filter.fy_start, fy_filter.fy_end
    ):
        gross_fy += Decimal(maturity["gross"])
        tax_fy += Decimal(maturity["tax"])
        net_fy += Decimal(maturity["net"])
        cash_part = maturity.get("interest_cash_amount")
        reinvest_part = maturity.get("reinvested_interest_amount")
        if cash_part is None or reinvest_part is None:
            split_known = False
        else:
            interest_cash_fy += Decimal(cash_part)
            reinvested_fy += Decimal(reinvest_part)

    return {
        "financial_year": fy_filter.label,
        "fy_start": fy_filter.fy_start.isoformat(),
        "fy_end": fy_filter.fy_end.isoformat(),
        "expected_gross_interest_fy": _decimal_to_json(expected_fy),
        "actual_gross_interest_fy": _decimal_to_json(gross_fy),
        "tax_withheld_fy": _decimal_to_json(tax_fy),
        "actual_net_interest_fy": _decimal_to_json(net_fy),
        "interest_cash_amount_fy": _optional_decimal_json(
            interest_cash_fy if split_known else None
        ),
        "reinvested_interest_amount_fy": _optional_decimal_json(
            reinvested_fy if split_known else None
        ),
        "variance_actual_vs_expected_fy": _decimal_to_json(gross_fy - expected_fy),
    }


def _available_financial_years(
    fd: FixedDeposit,
    payments: list[FixedDepositInterestPayment],
    *,
    extra_dates: list[date] | None = None,
) -> list[str]:
    dates = [fd.investment_date, fd.maturity_date]
    for payment in payments:
        if not payment.is_reversed:
            dates.append(payment.payment_date)
    if extra_dates:
        dates.extend(extra_dates)
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


def _pending_payout_for(fd: FixedDeposit) -> FixedDepositPendingPayout | None:
    return FixedDepositPendingPayout.objects.filter(fixed_deposit=fd).first()


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
    pending_payout = _pending_payout_for(fd)
    confirmed_payout = (
        pending_payout
        if pending_payout is not None
        and pending_payout.status == FixedDepositPendingPayoutStatus.CONFIRMED
        else None
    )
    maturity_interest = _maturity_interest_for_term(fd)
    # Pending estimates stay outside actual totals; confirmed actuals count once here.
    # Renewal + linked settlement interest also count once via maturity_interest.
    term_actual = _payment_summary(
        payments, confirmed_payout, maturity_interest=maturity_interest
    )
    fy_extra_dates: list[date] = []
    if maturity_interest.get("event_date") is not None:
        fy_extra_dates.append(maturity_interest["event_date"])
    if confirmed_payout is not None and confirmed_payout.payment_date is not None:
        fy_extra_dates.append(confirmed_payout.payment_date)
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
        "financial_year_options": _available_financial_years(
            fd, payments, extra_dates=fy_extra_dates
        ),
        "financial_year_summary": _fy_summary(
            schedule_rows=schedule_rows,
            payments=payments,
            fy_filter=fy_filter,
            confirmed_payout=confirmed_payout,
            maturity_interest=maturity_interest,
        ),
        "pending_payout": (
            pending_payout_summary(pending_payout) if pending_payout is not None else None
        ),
        "term_totals": {
            "expected_gross_interest": _decimal_to_json(term_schedule["expected_gross_interest"]),
            "actual_gross_interest": _decimal_to_json(term_actual["actual_gross_interest"]),
            "tax_withheld": _decimal_to_json(term_actual["tax_withheld"]),
            "actual_net_interest": _decimal_to_json(term_actual["actual_net_interest"]),
            "interest_cash_amount": _optional_decimal_json(
                term_actual["interest_cash_amount"]
            ),
            "reinvested_interest_amount": _optional_decimal_json(
                term_actual["reinvested_interest_amount"]
            ),
            "variance_actual_vs_expected": _decimal_to_json(
                term_actual["actual_gross_interest"] - term_schedule["expected_gross_interest"]
            ),
        },
        "detailed_calculation": _serialize_detailed_calculation(fd),
        "warnings": warnings,
    }
