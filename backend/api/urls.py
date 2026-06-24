from django.urls import include, path

from api.views import HealthView
from portfolios.holdings_views import PortfolioAssetDetailView, PortfolioHoldingsView
from portfolios.performance_views import PortfolioPerformanceView
from portfolios.summary_views import PortfolioSummaryView
from portfolios.views import PortfolioDetailView, PortfolioListCreateView
from settings_app.views import SettingsView
from market_data.views import (
    BenchmarkIndicesView,
    NavRefreshView,
    PortfolioForceSyncView,
    PricesRefreshView,
)
from transactions.views import (
    TransactionCsvImportCashPreviewView,
    TransactionCsvImportView,
    TransactionDetailView,
    TransactionFilterOptionsView,
    TransactionListCreateView,
)
from debt.report_views import FixedDepositInterestReportView

urlpatterns = [
    path("auth/", include("accounts.urls")),
    path("cash/", include("cash.urls")),
    path("", include("debt.urls")),
    path("analytics/", include("analytics.urls")),
    path("health", HealthView.as_view(), name="health"),
    path("settings", SettingsView.as_view(), name="settings"),
    path("portfolios", PortfolioListCreateView.as_view(), name="portfolio-list-create"),
    path(
        "portfolios/<int:portfolio_id>",
        PortfolioDetailView.as_view(),
        name="portfolio-detail",
    ),
    path(
        "portfolio/holdings",
        PortfolioHoldingsView.as_view(),
        name="portfolio-holdings",
    ),
    path(
        "portfolio/summary",
        PortfolioSummaryView.as_view(),
        name="portfolio-summary",
    ),
    path(
        "portfolio/performance",
        PortfolioPerformanceView.as_view(),
        name="portfolio-performance",
    ),
    path(
        "portfolio/assets/<str:asset_symbol>",
        PortfolioAssetDetailView.as_view(),
        name="portfolio-asset-detail",
    ),
    path("transactions", TransactionListCreateView.as_view(), name="transaction-list-create"),
    path(
        "transactions/filter-options",
        TransactionFilterOptionsView.as_view(),
        name="transaction-filter-options",
    ),
    path(
        "transactions/import-csv/preview-cash",
        TransactionCsvImportCashPreviewView.as_view(),
        name="transaction-import-csv-preview-cash",
    ),
    path(
        "transactions/import-csv",
        TransactionCsvImportView.as_view(),
        name="transaction-import-csv",
    ),
    path(
        "transactions/<int:transaction_id>",
        TransactionDetailView.as_view(),
        name="transaction-detail",
    ),
    path("prices/refresh", PricesRefreshView.as_view(), name="prices-refresh"),
    path("nav/refresh", NavRefreshView.as_view(), name="nav-refresh"),
    path("benchmarks/indices", BenchmarkIndicesView.as_view(), name="benchmark-indices"),
    path("portfolio/force-sync", PortfolioForceSyncView.as_view(), name="portfolio-force-sync"),
    path(
        "reports/fixed-deposit-interest",
        FixedDepositInterestReportView.as_view(),
        name="fixed-deposit-interest-report",
    ),
]
