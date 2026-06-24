"""FD interest and tax withheld report (read-only; no accounting changes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Q

from debt.models import (
    FixedDepositInterestPayment,
    FixedDepositRenewalGroup,
    FixedDepositSettlement,
    FixedDepositStatus,
)
from fx.lookup import convert_amount_with_fill
from portfolios.scope import ResolvedPortfolioScope

SourceType = Literal["INTEREST_PAYMENT", "SETTLEMENT", "RENEWAL"]
GroupByCode = Literal["year", "portfolio", "bank", "fd", "source", "none"]

FD_INTEREST_FX_WARNING = (
    "FX rates are missing for some report rows; converted totals may be partial."
)

SOURCE_LABELS = {
    "INTEREST_PAYMENT": "Interest payment",
    "SETTLEMENT": "Settlement",
    "RENEWAL": "Renewal",
}


@dataclass(frozen=True)
class InterestReportTotals:
    gross_interest: float
    tax_withheld: float
    net_interest: float
    currency: str
    display_currency: str | None
    row_count: int
    fx_status: str = "ok"


@dataclass(frozen=True)
class InterestReportGroupedTotal:
    group_key: str
    group_label: str
    gross_interest: float
    tax_withheld: float
    net_interest: float
    row_count: int


@dataclass(frozen=True)
class FixedDepositInterestReportResult:
    rows: list[dict]
    totals: InterestReportTotals
    grouped_totals: list[InterestReportGroupedTotal] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _interest_nonzero(
    gross: Decimal, tax: Decimal, net: Decimal
) -> bool:
    return gross > 0 or tax > 0 or net > 0


def _portfolio_filter(scope: ResolvedPortfolioScope, field_prefix: str = "") -> Q:
    prefix = f"{field_prefix}__" if field_prefix else ""
    if scope.kind == "single":
        return Q(**{f"{prefix}portfolio_id__in": scope.portfolio_ids})
    return Q()


def _exclude_cancelled(prefix: str = "fixed_deposit") -> Q:
    return ~Q(**{f"{prefix}__status": FixedDepositStatus.CANCELLED})


def _row_base(
    *,
    source_type: SourceType,
    source_id: int,
    row_date: date,
    fd,
    bank,
    currency: str,
    gross: Decimal,
    tax: Decimal,
    net: Decimal,
    comment: str,
) -> dict:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "date": row_date.isoformat(),
        "portfolio_id": fd.portfolio_id,
        "portfolio_name": fd.portfolio.name,
        "bank_account_id": bank.id,
        "bank_account_name": bank.name,
        "institution_name": fd.institution_name,
        "deposit_account_number": fd.deposit_account_number,
        "fixed_deposit_id": fd.id,
        "currency": currency,
        "gross_interest": float(gross),
        "tax_withheld": float(tax),
        "net_interest": float(net),
        "comment": comment or "",
    }


def _apply_display_conversion(
    rows: list[dict],
    *,
    display_currency: str | None,
) -> tuple[list[dict], list[str], str]:
    if not display_currency:
        for row in rows:
            row["display_currency"] = None
            row["gross_interest_display"] = None
            row["tax_withheld_display"] = None
            row["net_interest_display"] = None
        return rows, [], "ok"

    disp = display_currency.strip().upper()
    warnings: list[str] = []
    any_fx_missing = False
    out: list[dict] = []
    for row in rows:
        copied = dict(row)
        copied["display_currency"] = disp
        src_ccy = row["currency"]
        row_date = date.fromisoformat(row["date"])
        if src_ccy == disp:
            copied["gross_interest_display"] = row["gross_interest"]
            copied["tax_withheld_display"] = row["tax_withheld"]
            copied["net_interest_display"] = row["net_interest"]
        else:
            g, st_g = convert_amount_with_fill(
                row["gross_interest"], src_ccy, disp, row_date
            )
            t, st_t = convert_amount_with_fill(
                row["tax_withheld"], src_ccy, disp, row_date
            )
            n, st_n = convert_amount_with_fill(
                row["net_interest"], src_ccy, disp, row_date
            )
            if g is None or t is None or n is None:
                any_fx_missing = True
                copied["gross_interest_display"] = None
                copied["tax_withheld_display"] = None
                copied["net_interest_display"] = None
            else:
                copied["gross_interest_display"] = float(g)
                copied["tax_withheld_display"] = float(t)
                copied["net_interest_display"] = float(n)
                if "filled" in (st_g, st_t, st_n):
                    copied["fx_status"] = "filled"
                else:
                    copied["fx_status"] = "ok"
        out.append(copied)

    fx_status = "fx_unavailable" if any_fx_missing else "ok"
    if any_fx_missing:
        warnings.append(FD_INTEREST_FX_WARNING)
    return out, warnings, fx_status


def _sum_rows(
    rows: list[dict],
    *,
    display_currency: str | None,
    fx_status: str,
) -> InterestReportTotals:
    gross = Decimal("0")
    tax = Decimal("0")
    net = Decimal("0")
    count = 0
    currencies: set[str] = set()

    for row in rows:
        currencies.add(row["currency"])
        if display_currency:
            if row.get("gross_interest_display") is None:
                continue
            gross += Decimal(str(row["gross_interest_display"]))
            tax += Decimal(str(row["tax_withheld_display"]))
            net += Decimal(str(row["net_interest_display"]))
            count += 1
        else:
            gross += Decimal(str(row["gross_interest"]))
            tax += Decimal(str(row["tax_withheld"]))
            net += Decimal(str(row["net_interest"]))
            count += 1

    if display_currency:
        total_currency = display_currency.strip().upper()
    elif len(currencies) == 1:
        total_currency = next(iter(currencies))
    else:
        total_currency = "MIXED"

    return InterestReportTotals(
        gross_interest=float(gross),
        tax_withheld=float(tax),
        net_interest=float(net),
        currency=total_currency,
        display_currency=display_currency.strip().upper() if display_currency else None,
        row_count=count,
        fx_status=fx_status,
    )


def _group_rows(
    rows: list[dict],
    group_by: GroupByCode,
    *,
    display_currency: str | None,
) -> list[InterestReportGroupedTotal]:
    if group_by == "none":
        return []

    buckets: dict[str, dict] = {}
    for row in rows:
        if group_by == "year":
            key = row["date"][:4]
            label = key
        elif group_by == "portfolio":
            key = str(row["portfolio_id"])
            label = row["portfolio_name"]
        elif group_by == "bank":
            key = str(row["bank_account_id"])
            label = row["bank_account_name"]
        elif group_by == "fd":
            key = str(row["fixed_deposit_id"])
            label = f"{row['institution_name']} / {row['deposit_account_number']}"
        elif group_by == "source":
            key = row["source_type"]
            label = SOURCE_LABELS.get(row["source_type"], row["source_type"])
        else:
            continue

        if key not in buckets:
            buckets[key] = {
                "group_key": key,
                "group_label": label,
                "gross_interest": Decimal("0"),
                "tax_withheld": Decimal("0"),
                "net_interest": Decimal("0"),
                "row_count": 0,
            }
        bucket = buckets[key]
        if display_currency:
            if row.get("gross_interest_display") is None:
                continue
            bucket["gross_interest"] += Decimal(str(row["gross_interest_display"]))
            bucket["tax_withheld"] += Decimal(str(row["tax_withheld_display"]))
            bucket["net_interest"] += Decimal(str(row["net_interest_display"]))
        else:
            bucket["gross_interest"] += Decimal(str(row["gross_interest"]))
            bucket["tax_withheld"] += Decimal(str(row["tax_withheld"]))
            bucket["net_interest"] += Decimal(str(row["net_interest"]))
        bucket["row_count"] += 1

    return [
        InterestReportGroupedTotal(
            group_key=b["group_key"],
            group_label=b["group_label"],
            gross_interest=float(b["gross_interest"]),
            tax_withheld=float(b["tax_withheld"]),
            net_interest=float(b["net_interest"]),
            row_count=b["row_count"],
        )
        for b in sorted(buckets.values(), key=lambda x: x["group_key"])
    ]


def build_fixed_deposit_interest_report(
    user: AbstractBaseUser,
    scope: ResolvedPortfolioScope,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    display_currency: str | None = None,
    group_by: GroupByCode = "none",
) -> FixedDepositInterestReportResult:
    """Aggregate FD interest/tax rows from payments, settlements, and renewals."""
    rows: list[dict] = []

    payment_qs = (
        FixedDepositInterestPayment.objects.filter(user=user, is_reversed=False)
        .select_related("fixed_deposit", "fixed_deposit__portfolio", "bank_account")
        .filter(_exclude_cancelled())
    )
    payment_qs = payment_qs.filter(_portfolio_filter(scope, "fixed_deposit"))
    if start_date:
        payment_qs = payment_qs.filter(payment_date__gte=start_date)
    if end_date:
        payment_qs = payment_qs.filter(payment_date__lte=end_date)

    for payment in payment_qs.order_by("payment_date", "id"):
        rows.append(
            _row_base(
                source_type="INTEREST_PAYMENT",
                source_id=payment.id,
                row_date=payment.payment_date,
                fd=payment.fixed_deposit,
                bank=payment.bank_account,
                currency=payment.currency,
                gross=payment.gross_interest,
                tax=payment.tax_withheld,
                net=payment.net_interest,
                comment=payment.comment,
            )
        )

    renewal_settlement_ids = FixedDepositRenewalGroup.objects.filter(
        user=user
    ).values_list("settlement_id", flat=True)

    settlement_qs = (
        FixedDepositSettlement.objects.filter(user=user)
        .exclude(id__in=renewal_settlement_ids)
        .select_related("fixed_deposit", "fixed_deposit__portfolio", "bank_account")
        .filter(_exclude_cancelled())
        .filter(
            Q(gross_interest__gt=0)
            | Q(tax_withheld__gt=0)
            | Q(net_interest__gt=0)
        )
    )
    settlement_qs = settlement_qs.filter(_portfolio_filter(scope, "fixed_deposit"))
    if start_date:
        settlement_qs = settlement_qs.filter(settlement_date__gte=start_date)
    if end_date:
        settlement_qs = settlement_qs.filter(settlement_date__lte=end_date)

    for settlement in settlement_qs.order_by("settlement_date", "id"):
        rows.append(
            _row_base(
                source_type="SETTLEMENT",
                source_id=settlement.id,
                row_date=settlement.settlement_date,
                fd=settlement.fixed_deposit,
                bank=settlement.bank_account,
                currency=settlement.currency,
                gross=settlement.gross_interest,
                tax=settlement.tax_withheld,
                net=settlement.net_interest,
                comment=settlement.comment,
            )
        )

    renewal_qs = (
        FixedDepositRenewalGroup.objects.filter(user=user)
        .select_related(
            "old_fixed_deposit",
            "old_fixed_deposit__portfolio",
            "old_fixed_deposit__bank_account",
        )
        .filter(_exclude_cancelled("old_fixed_deposit"))
        .filter(
            Q(gross_interest__gt=0)
            | Q(tax_withheld__gt=0)
            | Q(net_interest__gt=0)
        )
    )
    if scope.kind == "single":
        renewal_qs = renewal_qs.filter(
            old_fixed_deposit__portfolio_id__in=scope.portfolio_ids
        )
    if start_date:
        renewal_qs = renewal_qs.filter(renewal_date__gte=start_date)
    if end_date:
        renewal_qs = renewal_qs.filter(renewal_date__lte=end_date)

    for renewal in renewal_qs.order_by("renewal_date", "id"):
        fd = renewal.old_fixed_deposit
        rows.append(
            _row_base(
                source_type="RENEWAL",
                source_id=renewal.id,
                row_date=renewal.renewal_date,
                fd=fd,
                bank=fd.bank_account,
                currency=renewal.currency,
                gross=renewal.gross_interest,
                tax=renewal.tax_withheld,
                net=renewal.net_interest,
                comment=renewal.comment,
            )
        )

    rows.sort(key=lambda r: (r["date"], r["source_type"], r["source_id"]))

    converted_rows, fx_warnings, fx_status = _apply_display_conversion(
        rows, display_currency=display_currency
    )
    totals = _sum_rows(
        converted_rows, display_currency=display_currency, fx_status=fx_status
    )
    grouped = _group_rows(
        converted_rows, group_by, display_currency=display_currency
    )

    warnings = list(fx_warnings)
    if not display_currency and len({r["currency"] for r in converted_rows}) > 1:
        warnings.append(
            "Multiple source currencies in report; totals are not combined. "
            "Pass display_currency to convert and sum."
        )

    return FixedDepositInterestReportResult(
        rows=converted_rows,
        totals=totals,
        grouped_totals=grouped,
        warnings=warnings,
    )
