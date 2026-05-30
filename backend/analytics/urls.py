from django.urls import path

from analytics.views import (
    AssetPerformanceMetricsView,
    CompareAnalyticsView,
    PortfolioPerformanceMetricsView,
)

urlpatterns = [
    path(
        "performance-metrics",
        PortfolioPerformanceMetricsView.as_view(),
        name="analytics-performance-metrics",
    ),
    path(
        "assets/<str:asset_symbol>/performance-metrics",
        AssetPerformanceMetricsView.as_view(),
        name="analytics-asset-performance-metrics",
    ),
    path(
        "compare",
        CompareAnalyticsView.as_view(),
        name="analytics-compare",
    ),
]
