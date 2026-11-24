"""
Authority checks for a user-confirmed provisional mutual-fund NAV (#50).

A provisional NAV may only be recorded on a manual BUY after this user's own
explicit exact-date fetch for the same scheme/date was unsuccessful, and only
while the exact-date provider cache is still missing. Reads the DB only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

from market_data.models import MutualFundNavFetchState
from market_data.nav_lookup import normalize_scheme_code
from transactions.mf_nav_validation import cached_nav_for_date
from transactions.models import MutualFundNavSource, MutualFundTransactionDetail
from transactions.services import TransactionValidationError

# Mirrors market_data.services.missing_nav_fetch.UNSUCCESSFUL_OUTCOMES.
UNSUCCESSFUL_FETCH_OUTCOMES = frozenset({"date_unavailable", "timeout", "provider_failure"})
ATTEMPT_MAX_AGE = timedelta(hours=24)

PROVISIONAL_FIELDS = (
    "provisional_nav",
    "provisional_attempt_id",
    "confirm_provisional_nav",
    "confirm_paid_value",
)


class ProvisionalNavError(TransactionValidationError):
    def __init__(self, message: str, *, code: str = "not_eligible"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProvisionalAuthority:
    nav: Decimal
    attempt_id: uuid.UUID | None
    failure_reason: str
    confirmed_at: Any
    reused: bool


def has_provisional_request(data: dict[str, Any]) -> bool:
    return any(data.get(name) not in (None, "", False) for name in PROVISIONAL_FIELDS)


def _now():
    return timezone.now()


def _parse_attempt_id(value) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ProvisionalNavError("provisional_attempt_id is not a valid attempt id") from exc


def parse_provisional_nav(value) -> Decimal:
    if value in (None, ""):
        raise ProvisionalNavError("provisional_nav is required", code="invalid")
    try:
        nav = Decimal(str(value))
    except Exception as exc:
        raise ProvisionalNavError("provisional_nav must be a number", code="invalid") from exc
    if not nav.is_finite() or nav <= 0:
        raise ProvisionalNavError("provisional_nav must be greater than 0", code="invalid")
    return nav


def reject_if_cache_available(scheme_code: str, nav_date: date) -> None:
    if cached_nav_for_date(scheme_code=scheme_code, nav_date=nav_date) is not None:
        raise ProvisionalNavError(
            f"Cached NAV is now available for scheme {scheme_code} on {nav_date}; "
            "save with the cached NAV instead of a provisional NAV.",
            code="cache_available",
        )


def require_unsuccessful_attempt(
    *,
    user_id: int | None,
    scheme_code: str,
    nav_date: date,
    attempt_id,
    lock: bool = False,
) -> MutualFundNavFetchState:
    """Return this user's latest unsuccessful fetch evidence for scheme/date, else raise."""
    attempt = _parse_attempt_id(attempt_id)
    if attempt is None:
        raise ProvisionalNavError(
            "A provisional NAV requires an unsuccessful exact-date NAV fetch for this scheme and date."
        )
    qs = MutualFundNavFetchState.objects
    if lock:
        qs = qs.select_for_update()
    state = qs.filter(scheme_code=normalize_scheme_code(scheme_code), nav_date=nav_date).first()
    if (
        state is None
        or user_id is None
        or state.last_attempt_id != attempt
        or state.last_attempt_user_id != user_id
        or state.last_outcome not in UNSUCCESSFUL_FETCH_OUTCOMES
    ):
        raise ProvisionalNavError(
            "No matching unsuccessful NAV fetch for this scheme and date. Fetch the missing NAV again."
        )
    if state.last_attempt_at is None or _now() - state.last_attempt_at > ATTEMPT_MAX_AGE:
        raise ProvisionalNavError(
            "The unsuccessful NAV fetch is too old. Fetch the missing NAV again.",
            code="stale_attempt",
        )
    return state


def _reusable_existing(
    existing: MutualFundTransactionDetail | None,
    *,
    scheme_code: str,
    nav_date: date,
    nav: Decimal,
) -> bool:
    return (
        existing is not None
        and existing.nav_source == MutualFundNavSource.PROVISIONAL_USER
        and existing.transaction.type == "BUY"
        and normalize_scheme_code(existing.transaction.asset_symbol) == scheme_code
        and existing.nav_date == nav_date
        and Decimal(existing.nav) == nav
    )


def resolve_provisional_authority(
    data: dict[str, Any],
    *,
    user_id: int | None,
    scheme_code: str,
    nav_date: date,
    txn_type: str,
    existing: MutualFundTransactionDetail | None = None,
    require_confirmations: bool = True,
    lock: bool = False,
) -> ProvisionalAuthority:
    """
    Validate a provisional NAV request. An existing provisional BUY keeps its authority
    while scheme, NAV date and provisional NAV are unchanged; any change needs a fresh
    unsuccessful attempt. The exact-date cache always wins.
    """
    if txn_type != "BUY":
        raise ProvisionalNavError("A provisional NAV can only be recorded on a mutual fund BUY.")
    nav = parse_provisional_nav(data.get("provisional_nav"))
    if require_confirmations and not (
        data.get("confirm_provisional_nav") is True and data.get("confirm_paid_value") is True
    ):
        raise ProvisionalNavError(
            "Confirm that the NAV is provisional and unverified, and that paid value is the "
            "actual payment.",
            code="confirmation_required",
        )
    reject_if_cache_available(scheme_code, nav_date)

    if data.get("provisional_attempt_id") in (None, "") and _reusable_existing(
        existing, scheme_code=scheme_code, nav_date=nav_date, nav=nav
    ):
        return ProvisionalAuthority(
            nav=nav,
            attempt_id=existing.provisional_attempt_id,
            failure_reason=existing.provisional_failure_reason,
            confirmed_at=existing.provisional_confirmed_at,
            reused=True,
        )

    state = require_unsuccessful_attempt(
        user_id=user_id,
        scheme_code=scheme_code,
        nav_date=nav_date,
        attempt_id=data.get("provisional_attempt_id"),
        lock=lock,
    )
    reject_if_cache_available(scheme_code, nav_date)
    return ProvisionalAuthority(
        nav=nav,
        attempt_id=state.last_attempt_id,
        failure_reason=state.last_outcome,
        confirmed_at=_now(),
        reused=False,
    )
