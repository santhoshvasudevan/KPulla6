from django.core.management.base import BaseCommand

from fx.services import sync_fx_rates


class Command(BaseCommand):
    help = "Incrementally sync FX rates for transaction/display currency pairs."

    def handle(self, *args, **options):
        result = sync_fx_rates()
        msg = (
            f"FX sync finished (success={result.success}, "
            f"pairs={result.pairs_attempted}"
        )
        if result.partial:
            msg += ", partial=True (some pairs missing provider data)"
        if result.success:
            self.stdout.write(self.style.SUCCESS(msg + ")"))
        else:
            self.stdout.write(self.style.WARNING(msg + ")"))
