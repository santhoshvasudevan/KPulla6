from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolios.holdings_service import HoldingsValidationError, validate_display_currency
from portfolios.scope import PortfolioScopeError, resolve_portfolio_scope
from portfolios.services import PortfolioNotFoundError
from portfolios.summary_service import build_portfolio_summary


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class PortfolioSummaryView(APIView):
    def get(self, request):
        portfolio_id_param = request.query_params.get("portfolio_id")
        portfolio_id: int | None = None
        if portfolio_id_param is not None:
            try:
                portfolio_id = int(portfolio_id_param)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "portfolio_id must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        display_currency = request.query_params.get("display_currency")
        if display_currency is None:
            from settings_app.services import get_settings

            display_currency = get_settings(request.user).display_currency
        try:
            display_currency = validate_display_currency(display_currency)
        except HoldingsValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        include_timeseries = _parse_bool(
            request.query_params.get("include_timeseries"), default=True
        )

        try:
            scope = resolve_portfolio_scope(
                request.user,
                portfolio_scope=request.query_params.get("portfolio_scope"),
                portfolio_id=portfolio_id,
            )
        except PortfolioScopeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        result = build_portfolio_summary(
            scope=scope,
            include_timeseries=include_timeseries,
            display_currency=display_currency,
            user=request.user,
        )

        payload = {
            "total_invested": result.total_invested,
            "current_value": result.current_value,
            "realized_pl": result.realized_pl,
            "unrealized_pl": result.unrealized_pl,
            "total_pl": result.total_pl,
            "xirr": result.xirr,
            "base_currency": result.base_currency,
            "display_currency": result.display_currency,
            "fx_status": result.fx_status,
            "timeseries": result.timeseries,
        }
        if result.warnings:
            payload["warnings"] = result.warnings
        return Response(payload)
