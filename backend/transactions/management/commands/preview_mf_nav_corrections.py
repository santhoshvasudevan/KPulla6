"""Read-only, user-scoped historical NAV review. There is deliberately no apply flag."""
import json

from django.core.management.base import BaseCommand

from transactions.mf_nav_validation import cached_nav_for_date
from transactions.models import MutualFundTransactionDetail


class Command(BaseCommand):
    help = "Preview historical MF NAV mismatches without changing transactions or cash."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)

    def handle(self, *args, **options):
        rows = MutualFundTransactionDetail.objects.filter(
            transaction__portfolio__user_id=options["user_id"]
        ).select_related("transaction").order_by("transaction_id")
        count = 0
        for detail in rows.iterator():
            txn = detail.transaction
            nav = cached_nav_for_date(scheme_code=txn.asset_symbol, nav_date=detail.nav_date)
            if nav is not None and nav == detail.nav and nav == txn.price_per_share:
                continue
            self.stdout.write(json.dumps({
                "transaction_id": txn.id, "scheme_code": txn.asset_symbol,
                "nav_date": detail.nav_date.isoformat(), "entered_nav": str(detail.nav),
                "cached_nav": str(nav) if nav is not None else None,
                "status": "NAV_MISSING" if nav is None else "NAV_MISMATCH",
                "statement_fields": "unchanged; review only",
            }))
            count += 1
        self.stdout.write(f"Review rows: {count}. No records changed.")
