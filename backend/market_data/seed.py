from market_data.models import BenchmarkIndexConfig

DEFAULT_BENCHMARK_INDICES: tuple[tuple[str, str, str | None], ...] = (
    ("^GSPC", "S&P 500", "USD"),
    ("^IXIC", "Nasdaq Composite", "USD"),
    ("^DJI", "Dow Jones Industrial Average", "USD"),
    ("^STOXX50E", "Euro Stoxx 50", "EUR"),
    ("^GDAXI", "DAX", "EUR"),
    ("^NSEI", "Nifty 50", "INR"),
    ("^BSESN", "BSE Sensex", "INR"),
)


def ensure_benchmark_indices() -> int:
    created_or_updated = 0
    for symbol, display_name, currency in DEFAULT_BENCHMARK_INDICES:
        _, created = BenchmarkIndexConfig.objects.update_or_create(
            symbol=symbol,
            defaults={
                "display_name": display_name,
                "enabled": True,
                "currency": currency,
                "source": "yfinance",
            },
        )
        if created:
            created_or_updated += 1
    return created_or_updated
