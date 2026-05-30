from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.services import (
    CompareSubjectsError,
    build_analytics_compare,
    build_asset_performance_metrics,
    build_portfolio_performance_metrics,
    parse_compare_subjects,
)
from finance.performance_range import (
    InvalidPerformanceRangeError,
    validate_performance_range,
)
from portfolios.holdings_service import (
    AssetDetailValidationError,
    AssetNotFoundError,
    HoldingsValidationError,
    validate_display_currency,
)
from portfolios.performance_service import BenchmarkConfigError
from portfolios.scope import PortfolioScopeError, resolve_portfolio_scope
from portfolios.services import PortfolioNotFoundError


def _parse_metrics_query(request):
    """Shared query parsing for portfolio and asset Metric Sheet endpoints."""
    range_param = request.query_params.get("range", "1Y")
    try:
        range_code = validate_performance_range(range_param)
    except InvalidPerformanceRangeError as exc:
        return None, Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

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

    display_currency = request.query_params.get("display_currency")
    if display_currency is None:
        from settings_app.services import get_settings

        display_currency = get_settings().display_currency
    try:
        display_currency = validate_display_currency(display_currency)
    except HoldingsValidationError as exc:
        return None, Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    benchmark = (request.query_params.get("benchmark") or "").strip()
    if benchmark.lower() in ("none", "null", ""):
        benchmark = None

    try:
        scope = resolve_portfolio_scope(
            portfolio_scope=request.query_params.get("portfolio_scope"),
            portfolio_id=portfolio_id,
        )
    except PortfolioScopeError as exc:
        return None, Response(
            {"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    except PortfolioNotFoundError as exc:
        return None, Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    return {
        "range_code": range_code,
        "display_currency": display_currency,
        "benchmark": benchmark,
        "scope": scope,
        "folio_number": request.query_params.get("folio_number"),
    }, None


class PortfolioPerformanceMetricsView(APIView):
    """GET /api/v1/analytics/performance-metrics — portfolio Metric Sheet."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        params, error_response = _parse_metrics_query(request)
        if error_response is not None:
            return error_response

        try:
            result = build_portfolio_performance_metrics(
                scope=params["scope"],
                range_code=params["range_code"],
                display_currency=params["display_currency"],
                benchmark_symbol=params["benchmark"],
            )
        except BenchmarkConfigError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(result.payload)


class AssetPerformanceMetricsView(APIView):
    """GET /api/v1/analytics/assets/{asset_symbol}/performance-metrics — asset Metric Sheet."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, asset_symbol: str):
        params, error_response = _parse_metrics_query(request)
        if error_response is not None:
            return error_response

        try:
            result = build_asset_performance_metrics(
                asset_symbol=asset_symbol,
                scope=params["scope"],
                range_code=params["range_code"],
                display_currency=params["display_currency"],
                benchmark_symbol=params["benchmark"],
                folio_number=params["folio_number"],
            )
        except AssetDetailValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except AssetNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except BenchmarkConfigError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(result.payload)


class CompareAnalyticsView(APIView):
    """GET /api/v1/analytics/compare — side-by-side asset Metric Sheet comparison."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            subjects = parse_compare_subjects(request.query_params.get("subjects"))
        except CompareSubjectsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        params, error_response = _parse_metrics_query(request)
        if error_response is not None:
            return error_response

        try:
            result = build_analytics_compare(
                subjects=subjects,
                scope=params["scope"],
                range_code=params["range_code"],
                display_currency=params["display_currency"],
                benchmark_symbol=params["benchmark"],
            )
        except AssetDetailValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except AssetNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except BenchmarkConfigError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(result.payload)
