from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolios.holdings_service import (
    AssetDetailValidationError,
    AssetNotFoundError,
    HoldingsValidationError,
    build_asset_detail,
    build_holdings,
    validate_display_currency,
)
from portfolios.scope import PortfolioScopeError, resolve_portfolio_scope
from portfolios.services import PortfolioNotFoundError


class PortfolioHoldingsView(APIView):
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
                request.user,
                portfolio_scope=request.query_params.get("portfolio_scope"),
                portfolio_id=portfolio_id,
            )
        except PortfolioScopeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        result = build_holdings(
            scope=scope, display_currency=display_currency, user=request.user
        )
        payload = {
            "fx_status": result.fx_status,
            "holdings": result.holdings,
            "allocation": result.allocation,
            "display_currency": result.display_currency,
        }
        if result.warnings:
            payload["warnings"] = result.warnings
        return Response(payload)


class PortfolioAssetDetailView(APIView):
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
                request.user,
                portfolio_scope=request.query_params.get("portfolio_scope"),
                portfolio_id=portfolio_id,
            )
        except PortfolioScopeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        folio_number = request.query_params.get("folio_number")

        try:
            detail = build_asset_detail(
                asset_symbol=asset_symbol,
                scope=scope,
                display_currency=display_currency,
                folio_number=folio_number,
            )
        except AssetDetailValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except AssetNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        payload = {
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
        if detail.asset_type == "MUTUAL_FUND":
            mf_fields = {
                "asset_type": detail.asset_type,
                "scheme_code": detail.scheme_code,
                "scheme_name": detail.scheme_name,
                "folio_number": detail.folio_number,
                "latest_nav": detail.latest_nav,
                "nav_status": detail.nav_status,
                "units": detail.units,
            }
            if detail.primary_asset_class is not None:
                mf_fields["primary_asset_class"] = detail.primary_asset_class
            if detail.classification_source is not None:
                mf_fields["classification_source"] = detail.classification_source
            if detail.classification_notes:
                mf_fields["classification_notes"] = detail.classification_notes
            payload.update(mf_fields)
        return Response(payload)
