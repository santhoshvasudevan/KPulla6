from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from debt.serializers import (
    BankAccountCreateSerializer,
    BankAccountSeedBalanceSerializer,
    BankAccountSerializer,
    BankAccountUpdateSerializer,
    CashMovementCreateSerializer,
    CashMovementSerializer,
    ReversalWriteSerializer,
    FixedDepositInterestPaymentSerializer,
    FixedDepositInterestPaymentWriteSerializer,
    FixedDepositSerializer,
    FixedDepositSettlementSerializer,
    FixedDepositRenewalWriteSerializer,
    FixedDepositSettlementWriteSerializer,
    FixedDepositCancelWriteSerializer,
    FixedDepositMaturityEstimateQuerySerializer,
    FixedDepositUpdateSerializer,
    FixedDepositWriteSerializer,
)
from datetime import date

from debt.bank_ledger_services import (
    CashMovementNotFoundError,
    CashMovementValidationError,
    DuplicateHistoricalSeedError,
    InsufficientBankBalanceError,
    OpeningBalanceAlreadySeededError,
    bank_account_has_ledger,
    compute_bank_account_balance,
    compute_bank_funding_balance,
    create_manual_cash_movement,
    get_cash_movement,
    latest_ledger_movement_date,
    list_cash_movements,
    opening_balance_is_seeded,
    seed_historical_bank_balance,
    seed_opening_balance,
)

from debt.cancellation_services import (
    FixedDepositCancellationError,
    cancel_fixed_deposit,
)
from debt.services import (
    BankAccountNotFoundError,
    BankAccountValidationError,
    FixedDepositNotFoundError,
    FixedDepositValidationError,
    create_bank_account,
    create_fixed_deposit,
    deactivate_bank_account,
    deactivate_fixed_deposit,
    list_active_bank_accounts,
    list_fixed_deposits,
    get_bank_account,
    get_fixed_deposit,
    update_bank_account,
    update_fixed_deposit,
)
from debt.interest_payment_services import (
    InterestPaymentNotFoundError,
    InterestPaymentValidationError,
    create_fixed_deposit_interest_payment,
    get_fixed_deposit_interest_payment,
    list_fixed_deposit_interest_payments,
)
from debt.reversal_services import (
    InterestPaymentReversalError,
    ReversalValidationError,
    reverse_cash_movement,
    reverse_fixed_deposit_interest_payment,
)
from debt.renewal_services import RenewalValidationError, renew_fixed_deposit
from debt.settlement_services import (
    SettlementNotFoundError,
    SettlementValidationError,
    create_fixed_deposit_settlement,
    get_fixed_deposit_settlement,
    list_fixed_deposit_settlements,
    mark_fixed_deposit_matured,
)
from portfolios.scope import PortfolioScopeError, resolve_portfolio_scope
from portfolios.services import PortfolioNotFoundError


def _parse_portfolio_id(request) -> int | None:
    raw = request.query_params.get("portfolio_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError("portfolio_id must be an integer")


class BankAccountListCreateView(APIView):
    def get(self, request):
        accounts = list_active_bank_accounts(request.user)
        return Response(BankAccountSerializer(accounts, many=True).data)

    def post(self, request):
        serializer = BankAccountCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            account = create_bank_account(request.user, **serializer.validated_data)
        except BankAccountValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            BankAccountSerializer(account).data,
            status=status.HTTP_201_CREATED,
        )


class BankAccountDetailView(APIView):
    def get(self, request, account_id: int):
        try:
            account = get_bank_account(request.user, account_id)
        except BankAccountNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(BankAccountSerializer(account).data)

    def put(self, request, account_id: int):
        serializer = BankAccountUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        payload = dict(serializer.validated_data)
        if "portfolio_id" in request.data:
            payload["portfolio_id"] = serializer.validated_data.get("portfolio_id")
        try:
            account = update_bank_account(
                request.user, account_id, **payload
            )
        except BankAccountNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except BankAccountValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BankAccountSerializer(account).data)

    def delete(self, request, account_id: int):
        try:
            account = deactivate_bank_account(request.user, account_id)
        except BankAccountNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(BankAccountSerializer(account).data)


class FixedDepositMaturityEstimateView(APIView):
    def get(self, request):
        serializer = FixedDepositMaturityEstimateQuerySerializer(
            data=request.query_params
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        from debt.fd_maturity_services import preview_maturity_estimate

        return Response(preview_maturity_estimate(**serializer.validated_data))


class FixedDepositListCreateView(APIView):
    def get(self, request):
        try:
            portfolio_id = _parse_portfolio_id(request)
        except ValueError as exc:
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

        fds = list_fixed_deposits(
            request.user, portfolio_ids=scope.portfolio_ids
        )
        return Response(FixedDepositSerializer(fds, many=True).data)

    def post(self, request):
        serializer = FixedDepositWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            fd = create_fixed_deposit(request.user, **serializer.validated_data)
        except InsufficientBankBalanceError as exc:
            return _insufficient_bank_balance_response(exc)
        except FixedDepositValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (BankAccountNotFoundError, FixedDepositNotFoundError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            FixedDepositSerializer(fd).data,
            status=status.HTTP_201_CREATED,
        )


class FixedDepositDetailView(APIView):
    def get(self, request, fd_id: int):
        try:
            fd = get_fixed_deposit(request.user, fd_id)
        except FixedDepositNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(FixedDepositSerializer(fd).data)

    def put(self, request, fd_id: int):
        serializer = FixedDepositUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            fd = update_fixed_deposit(
                request.user, fd_id, **serializer.validated_data
            )
        except FixedDepositNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except FixedDepositValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (BankAccountNotFoundError,) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(FixedDepositSerializer(fd).data)

    def delete(self, request, fd_id: int):
        try:
            fd = deactivate_fixed_deposit(request.user, fd_id)
        except FixedDepositNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except FixedDepositValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(FixedDepositSerializer(fd).data)


class FixedDepositInterestPaymentListCreateView(APIView):
    def get(self, request, fd_id: int):
        try:
            payments = list_fixed_deposit_interest_payments(request.user, fd_id)
        except FixedDepositNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(FixedDepositInterestPaymentSerializer(payments, many=True).data)

    def post(self, request, fd_id: int):
        serializer = FixedDepositInterestPaymentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = create_fixed_deposit_interest_payment(
                request.user,
                fd_id,
                **serializer.validated_data,
            )
        except FixedDepositNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except InterestPaymentValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        body = FixedDepositInterestPaymentSerializer(result.payment).data
        if result.warning:
            body["warning"] = result.warning
        return Response(body, status=status.HTTP_201_CREATED)


class FixedDepositInterestPaymentDetailView(APIView):
    def get(self, request, payment_id: int):
        try:
            payment = get_fixed_deposit_interest_payment(request.user, payment_id)
        except InterestPaymentNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(FixedDepositInterestPaymentSerializer(payment).data)

    def put(self, request, payment_id: int):
        return Response(
            {
                "detail": (
                    "Fixed deposit interest payments are immutable. "
                    "Use ADJUSTMENT entries to correct."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def patch(self, request, payment_id: int):
        return self.put(request, payment_id)

    def delete(self, request, payment_id: int):
        return Response(
            {
                "detail": (
                    "Fixed deposit interest payments cannot be deleted. "
                    "Record a reversal instead."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class FixedDepositInterestPaymentReverseView(APIView):
    def post(self, request, payment_id: int):
        serializer = ReversalWriteSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = reverse_fixed_deposit_interest_payment(
                request.user,
                payment_id,
                reversal_date=serializer.validated_data.get("reversal_date"),
                reason=serializer.validated_data["reason"],
            )
        except InterestPaymentNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except InsufficientBankBalanceError as exc:
            return _insufficient_bank_balance_response(exc)
        except InterestPaymentReversalError as exc:
            status_code = (
                status.HTTP_409_CONFLICT
                if "deferred" in str(exc).lower()
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({"detail": str(exc)}, status=status_code)
        account = get_bank_account(request.user, result.payment.bank_account_id)
        return Response(
            {
                "original": FixedDepositInterestPaymentSerializer(result.payment).data,
                "reversal_cash_movement_id": result.reversal_cash_movement.id,
                "reversed_by": result.reversal_cash_movement.id,
                "bank_account": BankAccountSerializer(account).data,
                "message": result.message,
            },
            status=status.HTTP_201_CREATED,
        )


class FixedDepositCancelView(APIView):
    def post(self, request, fd_id: int):
        serializer = FixedDepositCancelWriteSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            fd = cancel_fixed_deposit(
                request.user,
                fd_id,
                cancellation_date=serializer.validated_data.get("cancellation_date"),
            )
        except FixedDepositNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except FixedDepositCancellationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FixedDepositSerializer(fd).data)


class FixedDepositMarkMaturedView(APIView):
    def post(self, request, fd_id: int):
        try:
            fd = mark_fixed_deposit_matured(request.user, fd_id)
        except FixedDepositNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except SettlementValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FixedDepositSerializer(fd).data)


class FixedDepositSettlementListView(APIView):
    def get(self, request, fd_id: int):
        try:
            settlements = list_fixed_deposit_settlements(request.user, fd_id)
        except FixedDepositNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(FixedDepositSettlementSerializer(settlements, many=True).data)


class FixedDepositSettleView(APIView):
    def post(self, request, fd_id: int):
        serializer = FixedDepositSettlementWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = create_fixed_deposit_settlement(
                request.user,
                fd_id,
                **serializer.validated_data,
            )
        except FixedDepositNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except SettlementValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        body = FixedDepositSettlementSerializer(result.settlement).data
        body["fixed_deposit_status"] = result.fixed_deposit.status
        return Response(body, status=status.HTTP_201_CREATED)


class FixedDepositRenewView(APIView):
    def post(self, request, fd_id: int):
        serializer = FixedDepositRenewalWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = renew_fixed_deposit(request.user, fd_id, **serializer.validated_data)
        except FixedDepositNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except RenewalValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "renewal_id": result.renewal_group.id,
                "old_fixed_deposit": {
                    "id": result.old_fixed_deposit.id,
                    "status": result.old_fixed_deposit.status,
                },
                "new_fixed_deposit": {
                    "id": result.new_fixed_deposit.id,
                    "status": result.new_fixed_deposit.status,
                },
                "settlement_id": result.settlement.id,
                "direct_reinvest_amount": float(result.renewal_group.direct_reinvest_amount),
                "cash_payout_amount": float(result.renewal_group.cash_payout_amount),
                "gross_interest": float(result.renewal_group.gross_interest),
                "tax_withheld": float(result.renewal_group.tax_withheld),
                "net_interest": float(result.renewal_group.net_interest),
                "cash_movement_ids": result.cash_movement_ids,
                "currency": result.renewal_group.currency,
            },
            status=status.HTTP_201_CREATED,
        )


class FixedDepositSettlementDetailView(APIView):
    def get(self, request, settlement_id: int):
        try:
            settlement = get_fixed_deposit_settlement(request.user, settlement_id)
        except SettlementNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(FixedDepositSettlementSerializer(settlement).data)

    def put(self, request, settlement_id: int):
        return Response(
            {
                "detail": (
                    "Fixed deposit settlements are immutable. "
                    "Use ADJUSTMENT entries to correct."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def patch(self, request, settlement_id: int):
        return self.put(request, settlement_id)

    def delete(self, request, settlement_id: int):
        return Response(
            {
                "detail": (
                    "Fixed deposit settlements cannot be deleted. "
                    "Use ADJUSTMENT entries to correct."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


def _insufficient_bank_balance_response(exc: InsufficientBankBalanceError) -> Response:
    body = {
        "detail": str(exc),
        "required": float(exc.required),
        "available": float(exc.available),
        "available_as_of_date": float(exc.available_as_of_date),
        "shortfall": float(exc.shortfall),
        "currency": exc.currency,
    }
    if exc.current_balance is not None:
        body["current_balance"] = float(exc.current_balance)
    if exc.investment_date is not None:
        body["investment_date"] = exc.investment_date.isoformat()
    if exc.latest_ledger_balance_date is not None:
        body["latest_ledger_balance_date"] = exc.latest_ledger_balance_date.isoformat()
    if exc.bank_account_id is not None:
        body["bank_account_id"] = exc.bank_account_id
    if exc.suggested_seed_date is not None:
        body["suggested_seed_date"] = exc.suggested_seed_date.isoformat()
    if exc.suggested_seed_amount is not None:
        body["suggested_seed_amount"] = float(exc.suggested_seed_amount)
    if exc.hint:
        body["hint"] = exc.hint
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


def _cash_movement_error_response(exc: Exception) -> Response | None:
    if isinstance(exc, (CashMovementNotFoundError, BankAccountNotFoundError)):
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, OpeningBalanceAlreadySeededError):
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, InsufficientBankBalanceError):
        return _insufficient_bank_balance_response(exc)
    if isinstance(exc, (CashMovementValidationError, BankAccountValidationError)):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return None


class BankAccountBalanceView(APIView):
    def get(self, request, account_id: int):
        try:
            account = get_bank_account(request.user, account_id)
        except BankAccountNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        as_of_raw = request.query_params.get("as_of")
        as_of_date = None
        if as_of_raw:
            try:
                as_of_date = date.fromisoformat(as_of_raw)
            except ValueError:
                return Response(
                    {"detail": "as_of must be an ISO date (YYYY-MM-DD)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        current_balance = compute_bank_account_balance(account)
        latest_date = latest_ledger_movement_date(account)
        body = {
            "bank_account_id": account.id,
            "currency": account.currency,
            "current_balance": float(current_balance),
            "opening_balance": float(account.opening_balance),
            "opening_balance_seeded": opening_balance_is_seeded(account),
            "has_ledger_entries": bank_account_has_ledger(account),
            "balance_source": "ledger" if bank_account_has_ledger(account) else "manual",
            "latest_ledger_balance_date": (
                latest_date.isoformat() if latest_date is not None else None
            ),
        }
        if as_of_date is not None:
            body["as_of_date"] = as_of_date.isoformat()
            body["balance_as_of_date"] = float(
                compute_bank_funding_balance(account, as_of_date=as_of_date)
            )
        return Response(body)


class BankAccountSeedOpeningBalanceView(APIView):
    def post(self, request, account_id: int):
        try:
            movement = seed_opening_balance(request.user, account_id)
        except Exception as exc:
            response = _cash_movement_error_response(exc)
            if response is not None:
                return response
            raise
        account = get_bank_account(request.user, account_id)
        return Response(
            {
                "bank_account": BankAccountSerializer(account).data,
                "cash_movement": CashMovementSerializer(movement).data,
            },
            status=status.HTTP_201_CREATED,
        )


class BankAccountSeedBalanceView(APIView):
    def post(self, request, account_id: int):
        serializer = BankAccountSeedBalanceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = seed_historical_bank_balance(
                request.user,
                account_id,
                movement_date=serializer.validated_data["date"],
                amount=serializer.validated_data["amount"],
                reason=serializer.validated_data.get("reason") or "",
                note=serializer.validated_data.get("note") or "",
            )
        except BankAccountNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except DuplicateHistoricalSeedError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "existing_cash_movement_id": exc.existing_movement.id,
                    "existing_cash_movement_date": exc.existing_movement.movement_date.isoformat(),
                    "existing_cash_movement_amount": float(exc.existing_movement.amount),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            response = _cash_movement_error_response(exc)
            if response is not None:
                return response
            raise
        return Response(
            {
                "cash_movement": CashMovementSerializer(result.movement).data,
                "balance_as_of_date": float(result.balance_as_of_date),
                "as_of_date": result.as_of_date.isoformat(),
                "currency": result.currency,
            },
            status=status.HTTP_201_CREATED,
        )


class CashMovementListCreateView(APIView):
    def get(self, request):
        bank_account_id = request.query_params.get("bank_account_id")
        parsed_bank_id = None
        if bank_account_id is not None:
            try:
                parsed_bank_id = int(bank_account_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "bank_account_id must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))
        except (TypeError, ValueError):
            return Response(
                {"detail": "page and page_size must be integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = list_cash_movements(
            request.user,
            bank_account_id=parsed_bank_id,
            page=page,
            page_size=page_size,
        )
        return Response(
            {
                "items": CashMovementSerializer(result.items, many=True).data,
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "pages": result.pages,
            }
        )

    def post(self, request):
        serializer = CashMovementCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            movement = create_manual_cash_movement(
                request.user,
                bank_account_id=data["bank_account_id"],
                movement_type=data["movement_type"],
                amount=data["amount"],
                movement_date=data["movement_date"],
                direction=data.get("direction"),
                portfolio_id=data.get("portfolio_id"),
                description=data.get("description", ""),
            )
        except Exception as exc:
            response = _cash_movement_error_response(exc)
            if response is not None:
                return response
            raise
        return Response(
            CashMovementSerializer(movement).data,
            status=status.HTTP_201_CREATED,
        )


class CashMovementDetailView(APIView):
    def get(self, request, movement_id: int):
        try:
            movement = get_cash_movement(request.user, movement_id)
        except CashMovementNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(CashMovementSerializer(movement).data)

    def put(self, request, movement_id: int):
        return Response(
            {"detail": "Cash movements are immutable. Use ADJUSTMENT entries to correct."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def patch(self, request, movement_id: int):
        return self.put(request, movement_id)

    def delete(self, request, movement_id: int):
        return Response(
            {"detail": "Cash movements cannot be deleted. Use ADJUSTMENT entries to correct."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class CashMovementReverseView(APIView):
    def post(self, request, movement_id: int):
        serializer = ReversalWriteSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = reverse_cash_movement(
                request.user,
                movement_id,
                reversal_date=serializer.validated_data.get("reversal_date"),
                reason=serializer.validated_data["reason"],
            )
        except CashMovementNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except InsufficientBankBalanceError as exc:
            return _insufficient_bank_balance_response(exc)
        except ReversalValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        account = get_bank_account(request.user, result.original.bank_account_id)
        return Response(
            {
                "original": CashMovementSerializer(result.original).data,
                "reversal_cash_movement_id": result.reversal.id,
                "reversal": CashMovementSerializer(result.reversal).data,
                "reversed_by": result.reversal.id,
                "bank_account": BankAccountSerializer(account).data,
                "message": result.message,
            },
            status=status.HTTP_201_CREATED,
        )
