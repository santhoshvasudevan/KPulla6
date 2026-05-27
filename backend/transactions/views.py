from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolios.services import PortfolioNotFoundError
from transactions.models import MutualFundTransactionDetail
from transactions.mutual_fund_services import (
    create_mutual_fund_transaction,
    update_mutual_fund_transaction,
)
from transactions.serializers import (
    CsvImportResponseSerializer,
    MutualFundTransactionWriteSerializer,
    TransactionListSerializer,
    TransactionSerializer,
    TransactionWriteSerializer,
)
from transactions.services import (
    TransactionNotFoundError,
    TransactionValidationError,
    create_transaction,
    delete_transaction,
    get_transaction,
    import_transactions_from_csv,
    list_transactions,
    update_transaction,
)


class TransactionListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))
        except (TypeError, ValueError):
            return Response(
                {"detail": "page and page_size must be integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        portfolio_id = request.query_params.get("portfolio_id")
        parsed_portfolio_id = int(portfolio_id) if portfolio_id is not None else None

        try:
            result = list_transactions(
                page=page,
                page_size=page_size,
                asset_symbol=request.query_params.get("asset_symbol"),
                portfolio_scope=request.query_params.get("portfolio_scope"),
                portfolio_id=parsed_portfolio_id,
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except TransactionValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        payload = TransactionListSerializer(
            {
                "items": result.items,
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "pages": result.pages,
            }
        ).data
        return Response(payload)

    def post(self, request):
        if request.data.get("asset_type") == "MUTUAL_FUND":
            return self._post_mutual_fund(request)
        return self._post_stock(request)

    def _post_stock(self, request):
        serializer = TransactionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data.copy()
        portfolio_id = data.pop("portfolio_id", None)
        try:
            transaction = create_transaction(
                validated_data={**data, "portfolio_id": portfolio_id},
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except TransactionValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            TransactionSerializer(transaction).data,
            status=status.HTTP_201_CREATED,
        )

    def _post_mutual_fund(self, request):
        serializer = MutualFundTransactionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = create_mutual_fund_transaction(
                validated_data=serializer.validated_data,
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except TransactionValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {"detail": str(exc) or "Failed to save mutual fund transaction"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            TransactionSerializer(transaction).data,
            status=status.HTTP_201_CREATED,
        )


class TransactionDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def put(self, request, transaction_id: int):
        try:
            existing = get_transaction(transaction_id)
        except TransactionNotFoundError:
            return Response(
                {"detail": "Transaction not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_mutual_fund = request.data.get("asset_type") == "MUTUAL_FUND"
        if not is_mutual_fund:
            try:
                existing.mutual_fund_detail
                is_mutual_fund = True
            except MutualFundTransactionDetail.DoesNotExist:
                pass
        if is_mutual_fund:
            return self._put_mutual_fund(request, transaction_id)

        serializer = TransactionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data.copy()
        update_portfolio = "portfolio_id" in request.data

        try:
            transaction = update_transaction(
                transaction_id,
                validated_data=data,
                update_portfolio=update_portfolio,
            )
        except TransactionNotFoundError:
            return Response(
                {"detail": "Transaction not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except TransactionValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TransactionSerializer(transaction).data)

    def _put_mutual_fund(self, request, transaction_id: int):
        payload = request.data.copy()
        if "asset_type" not in payload:
            payload["asset_type"] = "MUTUAL_FUND"
        serializer = MutualFundTransactionWriteSerializer(data=payload)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        update_portfolio = "portfolio_id" in request.data
        try:
            transaction = update_mutual_fund_transaction(
                transaction_id,
                validated_data=serializer.validated_data,
                update_portfolio=update_portfolio,
            )
        except TransactionNotFoundError:
            return Response(
                {"detail": "Transaction not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except TransactionValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {"detail": str(exc) or "Failed to update mutual fund transaction"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(TransactionSerializer(transaction).data)

    def delete(self, request, transaction_id: int):
        try:
            delete_transaction(transaction_id)
        except TransactionNotFoundError:
            return Response(
                {"detail": "Transaction not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TransactionCsvImportView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            payload = {
                "success": False,
                "imported_count": 0,
                "errors": [{"row": 1, "field": "file", "message": "File is required"}],
            }
            return Response(
                CsvImportResponseSerializer(payload).data,
                status=status.HTTP_200_OK,
            )

        raw = upload.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            payload = {
                "success": False,
                "imported_count": 0,
                "errors": [
                    {"row": 1, "field": "file", "message": "File must be UTF-8 text"}
                ],
            }
            return Response(
                CsvImportResponseSerializer(payload).data,
                status=status.HTTP_200_OK,
            )

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

        try:
            result = import_transactions_from_csv(
                csv_text=text,
                portfolio_id=portfolio_id,
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            CsvImportResponseSerializer(
                {
                    "success": result.success,
                    "imported_count": result.imported_count,
                    "errors": result.errors,
                }
            ).data,
            status=status.HTTP_200_OK,
        )
