from datetime import date, datetime

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from cash.services import CashValidationError, InsufficientCashError
from portfolios.services import PortfolioNotFoundError
from transactions.models import MutualFundTransactionDetail
from transactions.mutual_fund_services import (
    create_mutual_fund_transaction,
    update_mutual_fund_transaction,
)
from transactions.csv_cash_preview import CsvImportCashPreviewRequired, preview_to_response_dict
from transactions.serializers import (
    CsvCashPreviewResponseSerializer,
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
    preview_csv_cash_for_import,
    update_transaction,
)


def _parse_date_param(value: str | None) -> date | None:
    if value is None or value == "":
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD.")


def _insufficient_cash_response(exc: InsufficientCashError) -> Response:
    return Response(
        {
            "detail": str(exc),
            "required": float(exc.required),
            "available": float(exc.available),
            "shortfall": float(exc.shortfall),
            "currency": exc.currency,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _transaction_write_error_response(exc: Exception) -> Response | None:
    if isinstance(exc, PortfolioNotFoundError):
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, InsufficientCashError):
        return _insufficient_cash_response(exc)
    if isinstance(exc, TransactionValidationError):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, CashValidationError):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return None


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
        except Exception as exc:
            err = _transaction_write_error_response(exc)
            if err is not None:
                return err
            raise

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
        except Exception as exc:
            err = _transaction_write_error_response(exc)
            if err is not None:
                return err
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
        except Exception as exc:
            err = _transaction_write_error_response(exc)
            if err is not None:
                return err
            raise

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
        except Exception as exc:
            err = _transaction_write_error_response(exc)
            if err is not None:
                return err
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
        except Exception as exc:
            err = _transaction_write_error_response(exc)
            if err is not None:
                return err
            raise
        return Response(status=status.HTTP_204_NO_CONTENT)


def _read_csv_upload(request) -> tuple[str | None, Response | None]:
    upload = request.FILES.get("file")
    if upload is None:
        payload = {
            "success": False,
            "imported_count": 0,
            "errors": [{"row": 1, "field": "file", "message": "File is required"}],
        }
        return None, Response(
            CsvImportResponseSerializer(payload).data,
            status=status.HTTP_200_OK,
        )

    raw = upload.read()
    try:
        return raw.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        payload = {
            "success": False,
            "imported_count": 0,
            "errors": [
                {"row": 1, "field": "file", "message": "File must be UTF-8 text"}
            ],
        }
        return None, Response(
            CsvImportResponseSerializer(payload).data,
            status=status.HTTP_200_OK,
        )


def _parse_portfolio_id_param(request) -> tuple[int | None, Response | None]:
    portfolio_id_param = request.query_params.get("portfolio_id")
    if portfolio_id_param is None:
        return None, None
    try:
        return int(portfolio_id_param), None
    except (TypeError, ValueError):
        return None, Response(
            {"detail": "portfolio_id must be an integer"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class TransactionCsvImportCashPreviewView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        text, err_response = _read_csv_upload(request)
        if err_response is not None:
            return err_response

        portfolio_id, bad = _parse_portfolio_id_param(request)
        if bad is not None:
            return bad

        try:
            preview = preview_csv_cash_for_import(
                request.user,
                csv_text=text,
                portfolio_id=portfolio_id,
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        if preview.row_errors:
            return Response(
                CsvImportResponseSerializer(
                    {
                        "success": False,
                        "imported_count": 0,
                        "errors": preview.row_errors,
                    }
                ).data,
                status=status.HTTP_200_OK,
            )

        return Response(
            CsvCashPreviewResponseSerializer(preview_to_response_dict(preview)).data,
            status=status.HTTP_200_OK,
        )


class TransactionCsvImportView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        text, err_response = _read_csv_upload(request)
        if err_response is not None:
            return err_response

        portfolio_id, bad = _parse_portfolio_id_param(request)
        if bad is not None:
            return bad

        create_cash_deposits = (
            request.query_params.get("create_cash_deposits", "").lower() == "true"
        )
        cash_preview_confirmed = (
            request.query_params.get("cash_preview_confirmed", "").lower() == "true"
        )

        try:
            result = import_transactions_from_csv(
                request.user,
                csv_text=text,
                portfolio_id=portfolio_id,
                create_cash_deposits=create_cash_deposits,
                cash_preview_confirmed=cash_preview_confirmed,
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except CsvImportCashPreviewRequired as exc:
            return Response(
                preview_to_response_dict(exc.preview),
                status=status.HTTP_409_CONFLICT,
            )

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
