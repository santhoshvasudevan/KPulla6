from django.core.management.base import BaseCommand

from market_data.nav_lookup import normalize_scheme_code
from market_data.services.mutual_fund_nav_sync import sync_mutual_fund_navs


class Command(BaseCommand):
    help = "Incrementally sync cached mutual fund NAVs for profiles in the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scheme-code",
            nargs="+",
            dest="scheme_codes",
            help="Optional AMFI scheme codes (must exist as MutualFundProfile rows)",
        )

    def handle(self, *args, **options):
        only = None
        if options.get("scheme_codes"):
            only = {normalize_scheme_code(c) for c in options["scheme_codes"]}
        result = sync_mutual_fund_navs(only_scheme_codes=only)
        style = self.style.SUCCESS if result.success else self.style.WARNING
        self.stdout.write(
            style(
                f"MF NAV sync finished (synced={result.synced}, "
                f"skipped={result.skipped}, failed={result.failed}, "
                f"success={result.success})"
            )
        )
