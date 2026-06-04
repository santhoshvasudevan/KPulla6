from datetime import date, datetime

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
    get_transaction_filter_options,
    import_transactions_from_csv,
    list_transactions,
    update_transaction,
)


def _parse_date_param(value: str | None) -> date | None:
    if value is None or value == "":
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD.")


def _parse_symbols_param(request) -> list[str] | None:
    raw = request.query_params.get("symbols")
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",")]
    cleaned = [p for p in parts if p]
    return cleaned or None


class TransactionListCreateView(APIView):
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
        try:
            parsed_portfolio_id = int(portfolio_id) if portfolio_id is not None else None
        except (TypeError, ValueError):
            return Response(
                {"detail": "portfolio_id must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date_after = _parse_date_param(request.query_params.get("date_after"))
            date_before = _parse_date_param(request.query_params.get("date_before"))
            date_from = _parse_date_param(request.query_params.get("date_from")) or date_after
            date_to = _parse_date_param(request.query_params.get("date_to")) or date_before
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if date_from is not None and date_to is not None and date_from > date_to:
            return Response(
                {"detail": "date_from must not be after date_to"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = list_transactions(
                request.user,
                page=page,
                page_size=page_size,
                asset_symbol=request.query_params.get("asset_symbol"),
                symbols=_parse_symbols_param(request),
                date_from=date_from,
                date_to=date_to,
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
                request.user,
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
                request.user,
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


class TransactionFilterOptionsView(APIView):
    def get(self, request):
        portfolio_id = request.query_params.get("portfolio_id")
        try:
            parsed_portfolio_id = int(portfolio_id) if portfolio_id is not None else None
        except (TypeError, ValueError):
            return Response(
                {"detail": "portfolio_id must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            options = get_transaction_filter_options(
                request.user,
                portfolio_scope=request.query_params.get("portfolio_scope"),
                portfolio_id=parsed_portfolio_id,
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except TransactionValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(
            {
                "portfolios": options.portfolios,
                "symbols": options.symbols,
                "types": options.types,
                "date_min": options.date_min,
                "date_max": options.date_max,
            }
        )


class TransactionDetailView(APIView):
    def put(self, request, transaction_id: int):
        try:
            existing = get_transaction(request.user, transaction_id)
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
                request.user,
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
                request.user,
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
            delete_transaction(request.user, transaction_id)
        except TransactionNotFoundError:
            return Response(
                {"detail": "Transaction not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TransactionCsvImportView(APIView):
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
                request.user,
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
