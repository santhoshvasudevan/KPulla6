from django.core.management.base import BaseCommand

from market_data.price_lookup import normalize_asset_symbol
from market_data.services.price_sync import sync_stock_prices


class Command(BaseCommand):
    help = "Incrementally sync historical stock prices for transaction symbols."

    def add_arguments(self, parser):
        parser.add_argument(
            "--symbols",
            nargs="+",
            help="Optional symbols (must exist in transactions)",
        )

    def handle(self, *args, **options):
        only = None
        if options.get("symbols"):
            only = {normalize_asset_symbol(s) for s in options["symbols"]}
        result = sync_stock_prices(only_symbols=only)
        self.stdout.write(
            self.style.SUCCESS(
                f"Price sync finished (success={result.success}, "
                f"symbols={result.symbols_synced})"
            )
        )
