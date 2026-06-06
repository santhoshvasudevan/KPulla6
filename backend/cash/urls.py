from django.urls import path

from cash.views import (
    CashBulkEntriesApplyView,
    CashBulkEntriesPreviewView,
    CashBalancesView,
    CashDepositView,
    CashLedgerEntryDetailView,
    CashLedgerView,
    CashTransferView,
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
    path("transfers", CashTransferView.as_view(), name="cash-transfers"),
    path(
        "bulk-entries/preview",
        CashBulkEntriesPreviewView.as_view(),
        name="cash-bulk-entries-preview",
    ),
    path(
        "bulk-entries/apply",
        CashBulkEntriesApplyView.as_view(),
        name="cash-bulk-entries-apply",
    ),
]
