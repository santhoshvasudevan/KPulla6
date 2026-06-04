from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolios.serializers import (
    PortfolioCreateSerializer,
    PortfolioSerializer,
    PortfolioUpdateSerializer,
)
from portfolios.services import (
    PortfolioNotFoundError,
    PortfolioValidationError,
    create_portfolio,
    deactivate_portfolio,
    list_active_portfolios,
    update_portfolio,
)


def _validation_response(exc: PortfolioValidationError) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _not_found_response(exc: PortfolioNotFoundError) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class PortfolioListCreateView(APIView):
    def get(self, request):
        portfolios = list_active_portfolios(request.user)
        return Response(PortfolioSerializer(portfolios, many=True).data)

    def post(self, request):
        serializer = PortfolioCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            portfolio = create_portfolio(request.user, **serializer.validated_data)
        except PortfolioValidationError as exc:
            return _validation_response(exc)
        return Response(
            PortfolioSerializer(portfolio).data,
            status=status.HTTP_201_CREATED,
        )


class PortfolioDetailView(APIView):
    def put(self, request, portfolio_id: int):
        serializer = PortfolioUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            portfolio = update_portfolio(
                request.user, portfolio_id, **serializer.validated_data
            )
        except PortfolioNotFoundError as exc:
            return _not_found_response(exc)
        except PortfolioValidationError as exc:
            return _validation_response(exc)
        return Response(PortfolioSerializer(portfolio).data)

    def delete(self, request, portfolio_id: int):
        try:
            portfolio = deactivate_portfolio(request.user, portfolio_id)
        except PortfolioNotFoundError as exc:
            return _not_found_response(exc)
        except PortfolioValidationError as exc:
            return _validation_response(exc)
        return Response(PortfolioSerializer(portfolio).data)
