from django.urls import path

from debt.views import (
    BankAccountDetailView,
    BankAccountListCreateView,
    BankAccountSeedOpeningBalanceView,
    CashMovementDetailView,
    CashMovementListCreateView,
    FixedDepositDetailView,
    FixedDepositInterestPaymentDetailView,
    FixedDepositInterestPaymentListCreateView,
    FixedDepositListCreateView,
    FixedDepositMarkMaturedView,
    FixedDepositSettleView,
    FixedDepositRenewView,
    FixedDepositSettlementDetailView,
    FixedDepositSettlementListView,
)

urlpatterns = [
    path("bank-accounts", BankAccountListCreateView.as_view(), name="bank-account-list"),
    path(
        "bank-accounts/<int:account_id>",
        BankAccountDetailView.as_view(),
        name="bank-account-detail",
    ),
    path(
        "bank-accounts/<int:account_id>/seed-opening-balance",
        BankAccountSeedOpeningBalanceView.as_view(),
        name="bank-account-seed-opening-balance",
    ),
    path("cash-movements", CashMovementListCreateView.as_view(), name="cash-movement-list"),
    path(
        "cash-movements/<int:movement_id>",
        CashMovementDetailView.as_view(),
        name="cash-movement-detail",
    ),
    path("fixed-deposits", FixedDepositListCreateView.as_view(), name="fixed-deposit-list"),
    path(
        "fixed-deposits/<int:fd_id>",
        FixedDepositDetailView.as_view(),
        name="fixed-deposit-detail",
    ),
    path(
        "fixed-deposits/<int:fd_id>/interest-payments",
        FixedDepositInterestPaymentListCreateView.as_view(),
        name="fixed-deposit-interest-payment-list",
    ),
    path(
        "fixed-deposit-interest-payments/<int:payment_id>",
        FixedDepositInterestPaymentDetailView.as_view(),
        name="fixed-deposit-interest-payment-detail",
    ),
    path(
        "fixed-deposits/<int:fd_id>/mark-matured",
        FixedDepositMarkMaturedView.as_view(),
        name="fixed-deposit-mark-matured",
    ),
    path(
        "fixed-deposits/<int:fd_id>/settle",
        FixedDepositSettleView.as_view(),
        name="fixed-deposit-settle",
    ),
    path(
        "fixed-deposits/<int:fd_id>/renew",
        FixedDepositRenewView.as_view(),
        name="fixed-deposit-renew",
    ),
    path(
        "fixed-deposits/<int:fd_id>/settlements",
        FixedDepositSettlementListView.as_view(),
        name="fixed-deposit-settlements-list",
    ),
    path(
        "fixed-deposit-settlements/<int:settlement_id>",
        FixedDepositSettlementDetailView.as_view(),
        name="fixed-deposit-settlement-detail",
    ),
]
