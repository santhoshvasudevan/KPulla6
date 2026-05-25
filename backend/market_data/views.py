from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from market_data.price_lookup import normalize_asset_symbol
from market_data.services.benchmark_sync import list_enabled_benchmark_indices
from market_data.services.market_data_sync import sync_all_market_data
from market_data.services.price_sync import sync_stock_prices


class PricesRefreshView(APIView):
    """
    Manual historical price refresh (synchronous).
    May call external market-data APIs; not used during holdings/dashboard reads.
    """

    def post(self, request: Request) -> Response:
        body = request.data if isinstance(request.data, dict) else {}
        raw_symbols = body.get("symbols")
        only_symbols = None
        if raw_symbols:
            only_symbols = {
                normalize_asset_symbol(s) for s in raw_symbols if s
            }
        sync_stock_prices(only_symbols=only_symbols)
        return Response(
            {"message": "Price sync scheduled"},
            status=status.HTTP_202_ACCEPTED,
        )


class BenchmarkIndicesView(APIView):
    def get(self, request: Request) -> Response:
        return Response({"indices": list_enabled_benchmark_indices()})


class PortfolioForceSyncView(APIView):
    """
    Alias for full market-data sync (stocks + benchmarks + FX).
    Runs synchronously in the request thread (no Celery/RQ).
    """

    def post(self, request: Request) -> Response:
        sync_all_market_data()
        return Response(
            {"message": "Sync started in background"},
            status=status.HTTP_202_ACCEPTED,
        )
