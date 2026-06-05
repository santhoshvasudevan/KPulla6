from django.urls import path

from cash.views import (
    CashBackfillApplyView,
    CashBackfillPreviewView,
    CashBalancesView,
    CashDepositView,
    CashLedgerEntryDetailView,
    CashLedgerView,
    CashWithdrawalView,
)

urlpatterns = [
    path("balances", CashBalancesView.as_view(), name="cash-balances"),
    path("ledger", CashLedgerView.as_view(), name="cash-ledger"),
    path(
        "ledger/<int:entry_id>",
        CashLedgerEntryDetailView.as_view(),
        name="cash-ledger-detail",
    ),
    path("deposits", CashDepositView.as_view(), name="cash-deposits"),
    path("withdrawals", CashWithdrawalView.as_view(), name="cash-withdrawals"),
    path(
        "backfill-preview",
        CashBackfillPreviewView.as_view(),
        name="cash-backfill-preview",
    ),
    path(
        "backfill-apply",
        CashBackfillApplyView.as_view(),
        name="cash-backfill-apply",
    ),
]
