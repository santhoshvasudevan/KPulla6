"""
Read-only historical NAV review classification (#53).

Compares a recorded MF transaction NAV with the exact-date provider cache. Never
writes, never calls providers, and never proposes new statement values: recorded
NAV, units, fees, paid value, provenance and settlements stay as recorded until
the user explicitly edits the transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from transactions.models import MutualFundNavSource

PROVISIONAL = "provisional"
LEGACY = "legacy"
MISSING = "missing"
CACHED_DISCREPANCY = "cached_discrepancy"
REVIEW_CLASSES = (PROVISIONAL, LEGACY, MISSING, CACHED_DISCREPANCY)


@dataclass(frozen=True)
class NavReview:
    review_class: str
    nav_source: str
    cached_nav: Decimal | None
    nav_difference: Decimal | None

    @property
    def reviewable(self) -> bool:
        """Only a cached exact-date NAV gives something to review against."""
        return self.review_class == CACHED_DISCREPANCY


def classify_nav_review(
    *,
    nav_source: str,
    recorded_nav: Decimal,
    price_per_share: Decimal,
    cached_nav: Decimal | None,
) -> NavReview | None:
    """Return the review state for one row, or None when nothing needs review."""
    provisional = nav_source == MutualFundNavSource.PROVISIONAL_USER
    if cached_nav is None:
        if provisional:
            review_class = PROVISIONAL
        elif nav_source == MutualFundNavSource.PROVIDER_CACHE:
            review_class = MISSING
        else:
            review_class = LEGACY
        return NavReview(review_class, nav_source, None, None)
    # A provisional row stays reviewable even when the provider later agrees: its
    # provenance only changes through an explicit edit, never on refresh or read.
    if not provisional and cached_nav == recorded_nav and cached_nav == price_per_share:
        return None
    return NavReview(CACHED_DISCREPANCY, nav_source, cached_nav, cached_nav - recorded_nav)
