from datetime import date, datetime

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from cash.bulk_entries import (
    BulkEntriesBlockedError,
    BulkEntriesValidationError,
    apply_bulk_cash_entries,
    bulk_entries_apply_to_response_dict,
    bulk_entries_preview_to_response_dict,
    preview_bulk_cash_entries,
)
from cash.serializers import (
    CashBulkEntriesApplyRequestSerializer,
    CashBulkEntriesRequestSerializer,
    CashDepositWriteSerializer,
    CashLedgerEntrySerializer,
    CashManualLedgerUpdateSerializer,
    CashTransferWriteSerializer,
    CashWithdrawalWriteSerializer,
)
from cash.services import (
    CashBalancesAllResult,
    CashBalancesSingleResult,
    CashEntryNotEditableError,
    CashValidationError,
    FutureCashImpactError,
    InsufficientCashError,
    cash_balances_for_scope,
    cash_transfer_response_payload,
    create_cash_deposit,
    create_cash_transfer,
    create_cash_withdrawal,
    delete_cash_ledger_entry,
    future_cash_impact_payload,
    list_cash_ledger_entries,
    update_cash_ledger_entry,
    validate_cash_currency,
    validate_entry_type,
)
from portfolios.scope import PortfolioScopeError, resolve_portfolio_scope
from portfolios.services import PortfolioNotFoundError, get_portfolio


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


def _future_cash_impact_response(exc: FutureCashImpactError) -> Response:
    return Response(
        future_cash_impact_payload(exc.impact),
        status=status.HTTP_409_CONFLICT,
    )


def _cash_write_error_response(exc: Exception) -> Response | None:
    if isinstance(exc, PortfolioNotFoundError):
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, InsufficientCashError):
        return _insufficient_cash_response(exc)
    if isinstance(exc, FutureCashImpactError):
        return _future_cash_impact_response(exc)
    if isinstance(exc, CashEntryNotEditableError):
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, CashValidationError):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return None


def _parse_date_param(value: str | None, *, param_name: str) -> date | None:
    if value is None or value == "":
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(
            f"Invalid date for {param_name} '{value}'. Use YYYY-MM-DD."
        )


def _parse_portfolio_id(request) -> int | None:
    raw = request.query_params.get("portfolio_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError("portfolio_id must be an integer")


class CashBalancesView(APIView):
    def get(self, request):
        try:
            portfolio_id = _parse_portfolio_id(request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            as_of_date = _parse_date_param(
                request.query_params.get("as_of_date"), param_name="as_of_date"
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        currency_param = request.query_params.get("currency")
        currency: str | None = None
        if currency_param is not None and currency_param != "":
            try:
                currency = validate_cash_currency(currency_param)
            except CashValidationError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            scope = resolve_portfolio_scope(
                request.user,
                portfolio_scope=request.query_params.get("portfolio_scope"),
                portfolio_id=portfolio_id,
            )
        except PortfolioScopeError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        result = cash_balances_for_scope(
            scope, as_of_date=as_of_date, currency=currency
        )

        if isinstance(result, CashBalancesSingleResult):
            return Response(
                {
                    "portfolio_id": result.portfolio_id,
                    "portfolio_name": result.portfolio_name,
                    "as_of_date": result.as_of_date.isoformat(),
                    "balances": [
                        {"currency": ccy, "balance": float(bal)}
                        for ccy, bal in result.balances
                    ],
                }
            )

        assert isinstance(result, CashBalancesAllResult)
        return Response(
            {
                "portfolio_scope": "all",
                "as_of_date": result.as_of_date.isoformat(),
                "balances": [
                    {
                        "portfolio_id": row.portfolio_id,
                        "portfolio_name": row.portfolio_name,
                        "currency": row.currency,
                        "balance": float(row.balance),
                    }
                    for row in result.balances
                ],
                "totals_by_currency": [
                    {"currency": ccy, "balance": float(bal)}
                    for ccy, bal in result.totals_by_currency
                ],
            }
        )


class CashLedgerView(APIView):
    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))
        except (TypeError, ValueError):
            return Response(
                {"detail": "page and page_size must be integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            portfolio_id = _parse_portfolio_id(request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            date_from = _parse_date_param(
                request.query_params.get("date_from"), param_name="date_from"
            )
            date_to = _parse_date_param(
                request.query_params.get("date_to"), param_name="date_to"
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        currency_param = request.query_params.get("currency")
        currency: str | None = None
        if currency_param is not None and currency_param != "":
            try:
                currency = validate_cash_currency(currency_param)
            except CashValidationError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        entry_type_param = request.query_params.get("entry_type")
        entry_type: str | None = None
        if entry_type_param is not None and entry_type_param != "":
            try:
                entry_type = validate_entry_type(entry_type_param)
            except CashValidationError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            scope = resolve_portfolio_scope(
                request.user,
                portfolio_scope=request.query_params.get("portfolio_scope"),
                portfolio_id=portfolio_id,
            )
        except PortfolioScopeError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = list_cash_ledger_entries(
                scope,
                currency=currency,
                entry_type=entry_type,
                date_from=date_from,
                date_to=date_to,
                page=page,
                page_size=page_size,
            )
        except CashValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "items": CashLedgerEntrySerializer(result.items, many=True).data,
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "pages": result.pages,
            }
        )


class CashDepositView(APIView):
    def post(self, request):
        serializer = CashDepositWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            entry = create_cash_deposit(
                request.user,
                portfolio_id=data["portfolio_id"],
                entry_date=data["date"],
                currency=data["currency"],
                amount=data["amount"],
                source_of_funds=data.get("source_of_funds", ""),
                note=data.get("note", ""),
            )
        except (PortfolioNotFoundError, CashValidationError, InsufficientCashError) as exc:
            err = _cash_write_error_response(exc)
            if err is not None:
                return err
            raise

        return Response(
            CashLedgerEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )


class CashWithdrawalView(APIView):
    def post(self, request):
        serializer = CashWithdrawalWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            entry = create_cash_withdrawal(
                request.user,
                portfolio_id=data["portfolio_id"],
                entry_date=data["date"],
                currency=data["currency"],
                amount=data["amount"],
                source_of_funds=data.get("source_of_funds", ""),
                note=data.get("note", ""),
            )
        except (PortfolioNotFoundError, CashValidationError, InsufficientCashError) as exc:
            err = _cash_write_error_response(exc)
            if err is not None:
                return err
            raise

        return Response(
            CashLedgerEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )


class CashTransferView(APIView):
    def post(self, request):
        serializer = CashTransferWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            result = create_cash_transfer(
                request.user,
                source_portfolio_id=data["source_portfolio_id"],
                target_portfolio_id=data["target_portfolio_id"],
                entry_date=data["date"],
                source_currency=data["source_currency"],
                source_amount=data["source_amount"],
                target_currency=data["target_currency"],
                target_amount=data["target_amount"],
                note=data.get("note", ""),
            )
        except (
            PortfolioNotFoundError,
            CashValidationError,
            InsufficientCashError,
            FutureCashImpactError,
        ) as exc:
            err = _cash_write_error_response(exc)
            if err is not None:
                return err
            raise

        return Response(
            cash_transfer_response_payload(result),
            status=status.HTTP_201_CREATED,
        )


class CashLedgerEntryDetailView(APIView):
    def put(self, request, entry_id: int):
        serializer = CashManualLedgerUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            entry = update_cash_ledger_entry(
                request.user,
                entry_id,
                entry_date=data["date"],
                currency=data["currency"],
                amount=data["amount"],
                source_of_funds=data.get("source_of_funds", ""),
                note=data.get("note", ""),
            )
        except (
            PortfolioNotFoundError,
            CashValidationError,
            InsufficientCashError,
            FutureCashImpactError,
        ) as exc:
            err = _cash_write_error_response(exc)
            if err is not None:
                return err
            raise

        return Response(CashLedgerEntrySerializer(entry).data)

    def delete(self, request, entry_id: int):
        try:
            delete_cash_ledger_entry(request.user, entry_id)
        except (PortfolioNotFoundError, CashValidationError, FutureCashImpactError) as exc:
            err = _cash_write_error_response(exc)
            if err is not None:
                return err
            raise

        return Response(status=status.HTTP_204_NO_CONTENT)


def _bulk_entries_validation_response(exc: CashValidationError) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _bulk_apply_confirmation_response(errors) -> Response | None:
    if isinstance(errors, dict) and errors.get("non_field_errors"):
        detail = errors["non_field_errors"][0]
        if isinstance(detail, str):
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(errors, list) and errors:
        return Response({"detail": str(errors[0])}, status=status.HTTP_400_BAD_REQUEST)
    return None


class CashBulkEntriesPreviewView(APIView):
    """POST /api/v1/cash/bulk-entries/preview — schedule manual cash rows (Cash-7D)."""

    def post(self, request):
        serializer = CashBulkEntriesRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            portfolio = get_portfolio(request.user, data["portfolio_id"])
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        if not portfolio.is_active:
            return Response(
                {"detail": f"Portfolio is inactive: {portfolio.id}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = preview_bulk_cash_entries(
                portfolio,
                entry_type=data["entry_type"],
                currency=data["currency"],
                amount=data["amount"],
                start_date=data["start_date"],
                end_date=data.get("end_date"),
                frequency=data["frequency"],
                source_of_funds=data.get("source_of_funds", ""),
                note=data.get("note", ""),
            )
        except (BulkEntriesValidationError, CashValidationError) as exc:
            return _bulk_entries_validation_response(exc)

        return Response(bulk_entries_preview_to_response_dict(result))


class CashBulkEntriesApplyView(APIView):
    """POST /api/v1/cash/bulk-entries/apply — confirmed bulk manual entries (Cash-7D)."""

    def post(self, request):
        serializer = CashBulkEntriesApplyRequestSerializer(data=request.data)
        if not serializer.is_valid():
            err = _bulk_apply_confirmation_response(serializer.errors)
            if err is not None:
                return err
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            portfolio = get_portfolio(request.user, data["portfolio_id"])
        except PortfolioNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        if not portfolio.is_active:
            return Response(
                {"detail": f"Portfolio is inactive: {portfolio.id}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = apply_bulk_cash_entries(
                portfolio,
                entry_type=data["entry_type"],
                currency=data["currency"],
                amount=data["amount"],
                start_date=data["start_date"],
                end_date=data.get("end_date"),
                frequency=data["frequency"],
                source_of_funds=data.get("source_of_funds", ""),
                note=data.get("note", ""),
            )
        except BulkEntriesBlockedError as exc:
            return Response(
                {"detail": str(exc), "warnings": exc.warnings},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (BulkEntriesValidationError, CashValidationError) as exc:
            return _bulk_entries_validation_response(exc)

        return Response(bulk_entries_apply_to_response_dict(result))
