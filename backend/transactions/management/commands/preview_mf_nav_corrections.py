"""Read-only, user-scoped historical NAV review. There is deliberately no apply flag."""
import json

from django.core.management.base import BaseCommand

from transactions.mf_nav_review import REVIEW_CLASSES, classify_nav_review
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
        counts = dict.fromkeys(REVIEW_CLASSES, 0)
        for detail in rows.iterator():
            txn = detail.transaction
            nav = cached_nav_for_date(scheme_code=txn.asset_symbol, nav_date=detail.nav_date)
            review = classify_nav_review(
                nav_source=detail.nav_source,
                recorded_nav=detail.nav,
                price_per_share=txn.price_per_share,
                cached_nav=nav,
            )
            if review is None:
                continue
            if nav is None:
                status = "NAV_MISSING"
            elif nav == detail.nav and nav == txn.price_per_share:
                status = "NAV_MATCH"
            else:
                status = "NAV_MISMATCH"
            self.stdout.write(json.dumps({
                "transaction_id": txn.id, "scheme_code": txn.asset_symbol,
                "nav_date": detail.nav_date.isoformat(), "entered_nav": str(detail.nav),
                "cached_nav": str(nav) if nav is not None else None,
                "status": status,
                "nav_source": review.nav_source,
                "review_class": review.review_class,
                "reviewable": review.reviewable,
                "nav_difference": (
                    str(review.nav_difference) if review.nav_difference is not None else None
                ),
                "statement_fields": "unchanged; review only",
            }))
            counts[review.review_class] += 1
        total = sum(counts.values())
        breakdown = ", ".join(f"{name}: {counts[name]}" for name in REVIEW_CLASSES)
        self.stdout.write(f"Review rows: {total} ({breakdown}). No records changed.")
