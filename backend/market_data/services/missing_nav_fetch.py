"""
Explicit exact-date MFAPI fetch for a confirmed missing mutual-fund NAV (#49).

Only the POST /nav/fetch-missing path calls this. It rechecks the cache, claims a
DB-backed in-flight slot per scheme/date, asks the provider for that single day,
and caches only a positive exact-date INR observation. Unsuccessful attempts start
a cooldown and record attempt evidence bound to the requesting user.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from market_data.models import Asset, AssetType, HistoricalPrice, MutualFundNavFetchState
from market_data.nav_lookup import normalize_scheme_code
from market_data.providers.amfi_nav_parser import normalize_api_scheme_code
from market_data.providers.mutual_fund_nav_provider import (
    AmfiNavTimeoutError,
    MutualFundNavProvider,
    default_mutual_fund_nav_provider,
)
from market_data.services.mutual_fund_nav_sync import MF_NAV_CURRENCY, upsert_mutual_fund_nav
from transactions.mf_nav_validation import cached_nav_for_date

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 60
IN_FLIGHT_TTL_SECONDS = 30

CACHE_HIT = "cache_hit"
FETCHED = "fetched"
DATE_UNAVAILABLE = "date_unavailable"
TIMEOUT = "timeout"
PROVIDER_FAILURE = "provider_failure"
IN_FLIGHT = "in_flight"
COOLDOWN = "cooldown"
UNSUCCESSFUL_OUTCOMES = {DATE_UNAVAILABLE, TIMEOUT, PROVIDER_FAILURE}


class MissingNavFetchRequestError(ValueError):
    """Request cannot be served (invalid input); never reaches the provider."""


class MissingNavFetchConflict(Exception):
    """A non-mutual-fund cache row already occupies this symbol/date."""


@dataclass(frozen=True)
class MissingNavFetchResult:
    scheme_code: str
    nav_date: date
    outcome: str
    nav: Decimal | None = None
    retry_after_seconds: int | None = None
    attempt_id: uuid.UUID | None = None

    def as_payload(self) -> dict:
        failed = self.outcome not in (CACHE_HIT, FETCHED)
        return {
            "scheme_code": self.scheme_code,
            "nav_date": self.nav_date.isoformat(),
            "outcome": self.outcome,
            "nav": str(self.nav) if self.nav is not None else None,
            "status": "available" if self.nav is not None else "missing",
            "retry_after_seconds": self.retry_after_seconds,
            "failure_category": self.outcome if failed else None,
            "attempt_id": str(self.attempt_id) if self.attempt_id else None,
        }


def _now() -> datetime:
    return timezone.now()


def _seconds_until(moment: datetime, now: datetime) -> int:
    return max(1, math.ceil((moment - now).total_seconds()))


def _validate(scheme_code: str, nav_date: date, now: datetime) -> str:
    scheme = normalize_api_scheme_code(normalize_scheme_code(scheme_code))
    if not scheme:
        raise MissingNavFetchRequestError("scheme_code must be a numeric AMFI scheme code")
    # Allow tomorrow (UTC) so IST same-day NAVs are not rejected around midnight.
    if nav_date > now.date() + timedelta(days=1):
        raise MissingNavFetchRequestError("nav_date cannot be in the future")
    return scheme


def _ensure_no_foreign_row(scheme: str, nav_date: date) -> None:
    if (
        HistoricalPrice.objects.filter(asset_symbol=scheme, date=nav_date)
        .exclude(asset_type=AssetType.MUTUAL_FUND)
        .exists()
    ):
        raise MissingNavFetchConflict(
            f"A non-mutual-fund price row already exists for {scheme} on {nav_date}"
        )


def _locked_state(scheme: str, nav_date: date) -> MutualFundNavFetchState:
    try:
        with transaction.atomic():
            MutualFundNavFetchState.objects.get_or_create(scheme_code=scheme, nav_date=nav_date)
    except IntegrityError:
        pass
    return MutualFundNavFetchState.objects.select_for_update().get(
        scheme_code=scheme, nav_date=nav_date
    )


def _claim(scheme: str, nav_date: date, user_id: int | None, now: datetime):
    """Return (claim_token, None) when this caller may fetch, else (None, result)."""
    with transaction.atomic():
        state = _locked_state(scheme, nav_date)
        cached = cached_nav_for_date(scheme_code=scheme, nav_date=nav_date)
        if cached is not None:
            return None, MissingNavFetchResult(scheme, nav_date, CACHE_HIT, nav=cached)
        if state.in_flight_until and state.in_flight_until > now:
            return None, MissingNavFetchResult(
                scheme, nav_date, IN_FLIGHT,
                retry_after_seconds=_seconds_until(state.in_flight_until, now),
            )
        if state.cooldown_until and state.cooldown_until > now:
            own = user_id is not None and state.last_attempt_user_id == user_id
            return None, MissingNavFetchResult(
                scheme, nav_date, COOLDOWN,
                retry_after_seconds=_seconds_until(state.cooldown_until, now),
                attempt_id=state.last_attempt_id if own else None,
            )
        token = uuid.uuid4()
        state.in_flight_until = now + timedelta(seconds=IN_FLIGHT_TTL_SECONDS)
        state.in_flight_token = token
        state.save(update_fields=["in_flight_until", "in_flight_token", "updated_at"])
        return token, None


def _fetch_exact(provider: MutualFundNavProvider, scheme: str, nav_date: date):
    """Return (outcome, nav). Only a single positive INR row for nav_date is accepted."""
    try:
        rows = provider.get_nav_history(scheme, nav_date, nav_date)
    except AmfiNavTimeoutError as exc:
        logger.warning("MFAPI timeout fetching NAV %s on %s: %s", scheme, nav_date, exc)
        return TIMEOUT, None
    except Exception as exc:
        logger.warning("MFAPI failure fetching NAV %s on %s: %s", scheme, nav_date, exc)
        return PROVIDER_FAILURE, None
    if not isinstance(rows, list):
        return PROVIDER_FAILURE, None
    exact = [row for row in rows if getattr(row, "date", None) == nav_date]
    if not exact:
        return DATE_UNAVAILABLE, None
    navs = set()
    for row in exact:
        try:
            nav = Decimal(str(row.nav))
        except Exception:
            return PROVIDER_FAILURE, None
        currency = (getattr(row, "currency", "") or "").strip().upper()
        if not nav.is_finite() or nav <= 0 or currency != MF_NAV_CURRENCY:
            return PROVIDER_FAILURE, None
        navs.add(nav)
    if len(navs) != 1:
        return PROVIDER_FAILURE, None
    return FETCHED, navs.pop()


def _finalize(scheme, nav_date, token, outcome, nav, user_id, now) -> MissingNavFetchResult:
    with transaction.atomic():
        state = MutualFundNavFetchState.objects.select_for_update().get(
            scheme_code=scheme, nav_date=nav_date
        )
        owns_claim = state.in_flight_token == token
        if outcome == FETCHED:
            asset = Asset.objects.filter(asset_type=AssetType.MUTUAL_FUND, symbol=scheme).first()
            upsert_mutual_fund_nav(
                scheme_code=scheme, row_date=nav_date, nav=nav,
                currency=MF_NAV_CURRENCY, asset=asset,
            )
            stored = cached_nav_for_date(scheme_code=scheme, nav_date=nav_date)
            if owns_claim:
                state.in_flight_until = None
                state.in_flight_token = None
                state.cooldown_until = None
                state.last_outcome = FETCHED
                state.last_failure_category = ""
                state.save()
            return MissingNavFetchResult(scheme, nav_date, FETCHED, nav=stored)

        attempt_id = uuid.uuid4()
        cooldown_until = now + timedelta(seconds=COOLDOWN_SECONDS)
        if owns_claim:
            state.in_flight_until = None
            state.in_flight_token = None
            state.cooldown_until = cooldown_until
            state.last_outcome = outcome
            state.last_failure_category = outcome
            state.last_attempt_id = attempt_id
            state.last_attempt_user_id = user_id
            state.last_attempt_at = now
            state.save()
        else:
            attempt_id = None
        return MissingNavFetchResult(
            scheme, nav_date, outcome,
            retry_after_seconds=COOLDOWN_SECONDS,
            attempt_id=attempt_id,
        )


def fetch_missing_mutual_fund_nav(
    *,
    scheme_code: str,
    nav_date: date,
    user_id: int | None,
    provider: MutualFundNavProvider | None = None,
) -> MissingNavFetchResult:
    """
    Fetch and cache one exact-date NAV after a confirmed cache miss.

    Database errors propagate (never treated as a cache miss). Provider errors
    are classified into timeout / provider_failure / date_unavailable.
    """
    now = _now()
    scheme = _validate(scheme_code, nav_date, now)

    cached = cached_nav_for_date(scheme_code=scheme, nav_date=nav_date)
    if cached is not None:
        return MissingNavFetchResult(scheme, nav_date, CACHE_HIT, nav=cached)
    _ensure_no_foreign_row(scheme, nav_date)

    token, early = _claim(scheme, nav_date, user_id, now)
    if early is not None:
        return early

    provider = provider or default_mutual_fund_nav_provider()
    outcome, nav = _fetch_exact(provider, scheme, nav_date)
    return _finalize(scheme, nav_date, token, outcome, nav, user_id, _now())
