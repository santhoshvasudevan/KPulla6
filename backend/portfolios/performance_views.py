from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolios.holdings_service import HoldingsValidationError, validate_display_currency
from portfolios.performance_service import (
    BenchmarkConfigError,
    build_portfolio_performance,
    build_portfolio_performance_with_benchmarks,
    performance_list_payload,
)
from portfolios.scope import PortfolioScopeError, resolve_portfolio_scope
from portfolios.services import PortfolioNotFoundError

VALID_METRICS = frozenset({"value", "cumulative_return", "twror"})


def _parse_benchmark_query(benchmark: str | None, benchmarks: str | None) -> str | None:
    raw = (benchmark or "").strip()
    if raw.lower() in ("none", "null"):
        return None
    if raw:
        return raw
    leg = (benchmarks or "").strip()
    if not leg or leg.lower() in ("none", "null"):
        return None
    return leg.split(",")[0].strip() or None


class PortfolioPerformanceView(APIView):
    def get(self, request):
        metric = (request.query_params.get("metric") or "value").strip().lower()
        if metric not in VALID_METRICS:
            return Response(
                {"detail": f"Invalid metric: {metric!r}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        range_param = request.query_params.get("range", "1Y")
        from finance.performance_range import (
            InvalidPerformanceRangeError,
            validate_performance_range,
        )

        try:
            range_code = validate_performance_range(range_param)
        except InvalidPerformanceRangeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

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

        bench = _parse_benchmark_query(
            request.query_params.get("benchmark"),
            request.query_params.get("benchmarks"),
        )

        if metric == "value":
            result = build_portfolio_performance(
                scope=scope,
                metric="value",
                range_code=range_code,
                display_currency=display_currency,
                user=request.user,
            )
            if result.warnings:
                return Response(
                    {
                        "points": performance_list_payload(result.points),
                        "warnings": result.warnings,
                    }
                )
            return Response(performance_list_payload(result.points))

        if bench:
            try:
                result = build_portfolio_performance_with_benchmarks(
                    scope=scope,
                    metric=metric,  # type: ignore[arg-type]
                    benchmark_symbol=bench,
                    range_code=range_code,
                    display_currency=display_currency,
                    user=request.user,
                )
            except BenchmarkConfigError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            payload: dict = {"series": result.series, "warnings": result.warnings}
            if result.metric:
                payload["metric"] = result.metric
            return Response(payload)

        result = build_portfolio_performance(
            scope=scope,
            metric=metric,  # type: ignore[arg-type]
            range_code=range_code,
            display_currency=display_currency,
            user=request.user,
        )
        if result.warnings:
            return Response(
                {
                    "points": performance_list_payload(result.points),
                    "warnings": result.warnings,
                }
            )
        return Response(performance_list_payload(result.points))
