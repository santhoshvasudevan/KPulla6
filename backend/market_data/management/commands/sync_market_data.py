from django.core.management.base import BaseCommand

from market_data.price_lookup import normalize_asset_symbol
from market_data.services.market_data_sync import sync_all_market_data


class Command(BaseCommand):
    help = "Sync stock prices, benchmark indices, FX rates, and mutual fund NAVs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--symbols",
            nargs="+",
            help="Optional stock symbols (must exist in transactions)",
        )
        parser.add_argument(
            "--skip-fx",
            action="store_true",
            help="Skip FX rate sync",
        )
        parser.add_argument(
            "--skip-mutual-funds",
            action="store_true",
            help="Skip mutual fund NAV sync",
        )

    def handle(self, *args, **options):
        only = None
        if options.get("symbols"):
            only = {normalize_asset_symbol(s) for s in options["symbols"]}
        result = sync_all_market_data(
            only_symbols=only,
            run_fx=not options.get("skip_fx"),
            run_mutual_funds=not options.get("skip_mutual_funds"),
        )
        msg = (
            f"Market data sync: prices={result.prices_success}, "
            f"benchmarks={result.benchmarks_success}, fx={result.fx_success}, "
            f"mutual_funds(synced={result.mutual_funds_synced}, "
            f"skipped={result.mutual_funds_skipped}, failed={result.mutual_funds_failed})"
        )
        if result.fx_partial:
            msg += " (fx partial — some pairs may lack provider data)"
        if result.success:
            self.stdout.write(self.style.SUCCESS(msg))
        else:
            self.stdout.write(self.style.WARNING(msg))
