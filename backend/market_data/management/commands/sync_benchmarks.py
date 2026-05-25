from django.core.management.base import BaseCommand

from market_data.services.benchmark_sync import sync_benchmark_prices


class Command(BaseCommand):
    help = "Incrementally sync enabled benchmark index prices (asset_type=INDEX)."

    def handle(self, *args, **options):
        ok = sync_benchmark_prices()
        if ok:
            self.stdout.write(self.style.SUCCESS("Benchmark sync finished"))
        else:
            self.stdout.write(self.style.WARNING("Benchmark sync completed with errors"))
