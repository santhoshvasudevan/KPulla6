from django.urls import path

from cash.views import (
    CashBalancesView,
    CashBulkEntriesApplyView,
    CashBulkEntriesPreviewView,
    CashDepositView,
    CashLedgerEntryDetailView,
    CashLedgerEntryReverseView,
    CashLedgerView,
    CashOverviewView,
    CashTransferView,
    CashWithdrawalView,
)

urlpatterns = [
    path("balances", CashBalancesView.as_view(), name="cash-balances"),
    path("overview", CashOverviewView.as_view(), name="cash-overview"),
    path("ledger", CashLedgerView.as_view(), name="cash-ledger"),
    path(
        "ledger/<int:entry_id>/reverse",
        CashLedgerEntryReverseView.as_view(),
        name="cash-ledger-reverse",
    ),
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
