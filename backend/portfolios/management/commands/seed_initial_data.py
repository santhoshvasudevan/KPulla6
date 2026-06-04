from django.core.management.base import BaseCommand

from accounts.services import get_or_create_initial_owner
from market_data.seed import ensure_benchmark_indices
from portfolios.seed import assert_no_virtual_portfolio_rows, ensure_default_portfolio
from settings_app.seed import ensure_app_settings


class Command(BaseCommand):
    help = "Idempotently seed Default Portfolio, AppSettings, and benchmark index config."

    def handle(self, *args, **options):
        owner = get_or_create_initial_owner()
        portfolio = ensure_default_portfolio(owner)
        settings = ensure_app_settings(owner)
        benchmark_count = ensure_benchmark_indices()
        assert_no_virtual_portfolio_rows()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: owner={owner.email}, default_portfolio_id={portfolio.id}, "
                f"settings_id={settings.id}, benchmark_symbols={benchmark_count} new rows"
            )
        )
