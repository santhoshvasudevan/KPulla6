"""Read-only FD report API views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.http import HttpResponse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from debt.interest_report_csv import (
    build_interest_report_csv,
    interest_report_csv_filename,
)
from debt.interest_report_service import GroupByCode, build_fixed_deposit_interest_report
from portfolios.holdings_service import HoldingsValidationError, validate_display_currency
from portfolios.scope import PortfolioScopeError, ResolvedPortfolioScope, resolve_portfolio_scope
from portfolios.services import PortfolioNotFoundError


def _parse_date(value: str | None, *, param: str) -> tuple[date | None, str | None]:
    if value is None or not str(value).strip():
        return None, None
    try:
        return date.fromisoformat(str(value).strip()), None
    except ValueError:
        return None, f"{param} must be an ISO date (YYYY-MM-DD)"


def _parse_group_by(value: str | None) -> tuple[GroupByCode, str | None]:
    if value is None or not str(value).strip():
        return "none", None
    code = str(value).strip().lower()
    allowed = {"year", "portfolio", "bank", "fd", "source", "none"}
    if code not in allowed:
        return "none", f"group_by must be one of: {', '.join(sorted(allowed))}"
    return code, None  # type: ignore[return-value]


@dataclass(frozen=True)
class ParsedReportQuery:
    scope: ResolvedPortfolioScope
    start_date: date | None
    end_date: date | None
    display_currency: str | None
    group_by: GroupByCode


def parse_report_query(request: Request) -> tuple[ParsedReportQuery | None, Response | None]:
    portfolio_id_param = request.query_params.get("portfolio_id")
    portfolio_id: int | None = None
    if portfolio_id_param is not None:
        try:
            portfolio_id = int(portfolio_id_param)
        except (TypeError, ValueError):
            return None, Response(
                {"detail": "portfolio_id must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    start_date, start_err = _parse_date(
        request.query_params.get("start_date"), param="start_date"
    )
    if start_err:
        return None, Response({"detail": start_err}, status=status.HTTP_400_BAD_REQUEST)
    end_date, end_err = _parse_date(
        request.query_params.get("end_date"), param="end_date"
    )
    if end_err:
        return None, Response({"detail": end_err}, status=status.HTTP_400_BAD_REQUEST)
    if start_date and end_date and start_date > end_date:
        return None, Response(
            {"detail": "start_date must not be after end_date"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    group_by, group_err = _parse_group_by(request.query_params.get("group_by"))
    if group_err:
        return None, Response({"detail": group_err}, status=status.HTTP_400_BAD_REQUEST)

    display_currency = request.query_params.get("display_currency")
    if display_currency is not None:
        try:
            display_currency = validate_display_currency(display_currency)
        except HoldingsValidationError as exc:
            return None, Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        scope = resolve_portfolio_scope(
            request.user,
            portfolio_scope=request.query_params.get("portfolio_scope"),
            portfolio_id=portfolio_id,
        )
    except PortfolioScopeError as exc:
        return None, Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except PortfolioNotFoundError as exc:
        return None, Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    return (
        ParsedReportQuery(
            scope=scope,
            start_date=start_date,
            end_date=end_date,
            display_currency=display_currency,
            group_by=group_by,
        ),
        None,
    )


class FixedDepositInterestReportView(APIView):
    """GET /api/v1/reports/fixed-deposit-interest — FD interest and tax withheld report."""

    def get(self, request):
        parsed, error = parse_report_query(request)
        if error is not None:
            return error

        result = build_fixed_deposit_interest_report(
            request.user,
            parsed.scope,
            start_date=parsed.start_date,
            end_date=parsed.end_date,
            display_currency=parsed.display_currency,
            group_by=parsed.group_by,
        )

        payload: dict = {
            "rows": result.rows,
            "totals": {
                "gross_interest": result.totals.gross_interest,
                "tax_withheld": result.totals.tax_withheld,
                "net_interest": result.totals.net_interest,
                "currency": result.totals.currency,
                "display_currency": result.totals.display_currency,
                "row_count": result.totals.row_count,
                "fx_status": result.totals.fx_status,
            },
        }
        if result.grouped_totals:
            payload["grouped_totals"] = [
                {
                    "group_key": g.group_key,
                    "group_label": g.group_label,
                    "gross_interest": g.gross_interest,
                    "tax_withheld": g.tax_withheld,
                    "net_interest": g.net_interest,
                    "row_count": g.row_count,
                }
                for g in result.grouped_totals
            ]
        if result.warnings:
            payload["warnings"] = result.warnings
        return Response(payload)


class FixedDepositInterestReportExportView(APIView):
    """GET /api/v1/reports/fixed-deposit-interest/export.csv — CSV export (detail rows)."""

    def get(self, request):
        parsed, error = parse_report_query(request)
        if error is not None:
            return error

        result = build_fixed_deposit_interest_report(
            request.user,
            parsed.scope,
            start_date=parsed.start_date,
            end_date=parsed.end_date,
            display_currency=parsed.display_currency,
            group_by="none",
        )
        csv_text = build_interest_report_csv(result)
        filename = interest_report_csv_filename(
            start_date=parsed.start_date,
            end_date=parsed.end_date,
        )
        response = HttpResponse(csv_text, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
