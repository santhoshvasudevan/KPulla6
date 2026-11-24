from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers

from market_data.nav_refresh import market_data_sync_response_payload, run_mutual_fund_nav_refresh
from market_data.price_lookup import normalize_asset_symbol
from market_data.services.benchmark_sync import list_enabled_benchmark_indices
from market_data.services.market_data_sync import sync_all_market_data
from market_data.services.price_sync import sync_stock_prices


class NavLookupView(APIView):
    """Read an exact-date INR NAV from cache; never contact a provider."""

    def get(self, request: Request) -> Response:
        from transactions.mf_nav_validation import cached_nav_for_date
        from market_data.nav_lookup import normalize_scheme_code

        class Query(serializers.Serializer):
            scheme_code = serializers.CharField(max_length=32)
            nav_date = serializers.DateField()

        query = Query(data=request.query_params)
        query.is_valid(raise_exception=True)
        scheme = normalize_scheme_code(query.validated_data["scheme_code"])
        if not scheme:
            return Response({"detail": "scheme_code is required"}, status=400)
        day = query.validated_data["nav_date"]
        nav = cached_nav_for_date(scheme_code=scheme, nav_date=day)
        return Response({"scheme_code": scheme, "nav_date": day.isoformat(),
                         "nav": str(nav) if nav is not None else None,
                         "status": "available" if nav is not None else "missing"})


class NavFetchMissingView(APIView):
    """Explicit exact-date MFAPI fetch after a confirmed NAV cache miss; never writes transactions."""

    def post(self, request: Request) -> Response:
        from market_data.services.missing_nav_fetch import (
            MissingNavFetchConflict,
            MissingNavFetchRequestError,
            fetch_missing_mutual_fund_nav,
        )

        class Body(serializers.Serializer):
            scheme_code = serializers.CharField(max_length=32)
            nav_date = serializers.DateField()

        body = Body(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            result = fetch_missing_mutual_fund_nav(
                scheme_code=body.validated_data["scheme_code"],
                nav_date=body.validated_data["nav_date"],
                user_id=request.user.id,
            )
        except MissingNavFetchRequestError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except MissingNavFetchConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(result.as_payload())


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


class NavRefreshView(APIView):
    """
    Manual mutual fund NAV refresh (synchronous).
    May call external NAV provider; not used during holdings/dashboard reads.
    """

    def post(self, request: Request) -> Response:
        body = request.data if isinstance(request.data, dict) else {}
        raw_codes = body.get("scheme_codes")
        scheme_codes = None
        if raw_codes:
            scheme_codes = [str(c) for c in raw_codes if c]
        payload = run_mutual_fund_nav_refresh(scheme_codes=scheme_codes)
        return Response(payload, status=status.HTTP_202_ACCEPTED)


class BenchmarkIndicesView(APIView):
    def get(self, request: Request) -> Response:
        return Response({"indices": list_enabled_benchmark_indices()})


class PortfolioForceSyncView(APIView):
    """
    Full market-data sync: stock prices + benchmark indices + FX + mutual fund NAVs.
    Runs synchronously in the request thread (no Celery/RQ).
    """

    def post(self, request: Request) -> Response:
        result = sync_all_market_data()
        return Response(
            market_data_sync_response_payload(result),
            status=status.HTTP_202_ACCEPTED,
        )
