from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolios.holdings_service import (
    AssetNotFoundError,
    HoldingsValidationError,
    build_asset_detail,
    build_holdings,
    validate_display_currency,
)
from portfolios.scope import PortfolioScopeError, resolve_portfolio_scope
from portfolios.services import PortfolioNotFoundError


class PortfolioHoldingsView(APIView):
    authentication_classes = []
    permission_classes = []

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

        display_currency = request.query_params.get("display_currency", "EUR")
        try:
            display_currency = validate_display_currency(display_currency)
        except HoldingsValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            scope = resolve_portfolio_scope(
                portfolio_scope=request.query_params.get("portfolio_scope"),
                portfolio_id=portfolio_id,
            )
        except PortfolioScopeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        result = build_holdings(scope=scope, display_currency=display_currency)
        return Response(
            {
                "fx_status": result.fx_status,
                "holdings": result.holdings,
                "display_currency": result.display_currency,
            }
        )


class PortfolioAssetDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, asset_symbol: str):
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

        display_currency = request.query_params.get("display_currency", "EUR")
        try:
            display_currency = validate_display_currency(display_currency)
        except HoldingsValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            scope = resolve_portfolio_scope(
                portfolio_scope=request.query_params.get("portfolio_scope"),
                portfolio_id=portfolio_id,
            )
        except PortfolioScopeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        try:
            detail = build_asset_detail(
                asset_symbol=asset_symbol,
                scope=scope,
                display_currency=display_currency,
            )
        except AssetNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "asset_symbol": detail.asset_symbol,
                "currency": detail.currency,
                "current_price": detail.current_price,
                "price_status": detail.price_status,
                "current_value": detail.current_value,
                "cumulative_qty": detail.cumulative_qty,
                "cumulative_invested_amount": detail.cumulative_invested_amount,
                "avg_cost_per_share": detail.avg_cost_per_share,
                "realized_pl": detail.realized_pl,
                "unrealized_pl": detail.unrealized_pl,
                "xirr": detail.xirr,
                "holding_status": detail.holding_status,
                "fx_status": detail.fx_status,
                "warnings": detail.warnings,
                "transactions": detail.transactions,
            }
        )
