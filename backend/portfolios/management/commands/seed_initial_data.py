from django.core.management.base import BaseCommand

from market_data.seed import ensure_benchmark_indices
from portfolios.seed import assert_no_virtual_portfolio_rows, ensure_default_portfolio
from settings_app.seed import ensure_app_settings


class Command(BaseCommand):
    help = "Idempotently seed Default Portfolio, AppSettings, and benchmark index config."

    def handle(self, *args, **options):
        portfolio = ensure_default_portfolio()
        settings = ensure_app_settings()
        benchmark_count = ensure_benchmark_indices()
        assert_no_virtual_portfolio_rows()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: default_portfolio_id={portfolio.id}, "
                f"settings_id={settings.id}, benchmark_symbols={benchmark_count} new rows"
            )
        )
