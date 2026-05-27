from __future__ import annotations

from typing import Optional

from market_data.nav_lookup import normalize_scheme_code
from market_data.services.mutual_fund_nav_sync import MutualFundNavSyncResult, sync_mutual_fund_navs


def mutual_fund_nav_sync_warnings(result: MutualFundNavSyncResult) -> list[str]:
    warnings: list[str] = []
    if result.failed:
        warnings.append(
            f"NAV sync failed for {result.failed} scheme(s); check logs for details."
        )
    if result.skipped:
        warnings.append(
            f"Skipped {result.skipped} scheme(s) with no transaction anchor or cached NAV."
        )
    return warnings


def run_mutual_fund_nav_refresh(
    *,
    scheme_codes: Optional[list[str]] = None,
) -> dict:
    only: set[str] | None = None
    if scheme_codes:
        only = {normalize_scheme_code(c) for c in scheme_codes if c}
        only = {c for c in only if c}
    result = sync_mutual_fund_navs(only_scheme_codes=only)
    warnings = mutual_fund_nav_sync_warnings(result)
    return {
        "message": "Mutual fund NAV sync completed",
        "synced": result.synced,
        "skipped": result.skipped,
        "failed": result.failed,
        "warnings": warnings,
    }


def market_data_sync_response_payload(result) -> dict:
    """Build API payload for full market-data sync (stocks + benchmarks + FX + MF NAV)."""
    warnings: list[str] = []
    if getattr(result, "fx_partial", False):
        warnings.append("FX sync partial — some currency pairs may lack provider data.")
    mf_failed = getattr(result, "mutual_funds_failed", 0)
    mf_skipped = getattr(result, "mutual_funds_skipped", 0)
    if mf_failed:
        warnings.append(
            f"Mutual fund NAV sync failed for {mf_failed} scheme(s); check logs for details."
        )
    if mf_skipped:
        warnings.append(
            f"Skipped {mf_skipped} mutual fund scheme(s) with no anchor date."
        )
    if not result.prices_success:
        warnings.append("Stock price sync reported failures for one or more symbols.")
    if not result.benchmarks_success:
        warnings.append("Benchmark index sync reported failures.")
    if not result.fx_success:
        warnings.append("FX rate sync failed.")

    return {
        "message": "Sync started in background",
        "prices_success": result.prices_success,
        "benchmarks_success": result.benchmarks_success,
        "fx_success": result.fx_success,
        "fx_partial": result.fx_partial,
        "mutual_funds": {
            "synced": getattr(result, "mutual_funds_synced", 0),
            "skipped": mf_skipped,
            "failed": mf_failed,
            "success": getattr(result, "mutual_funds_success", True),
        },
        "warnings": warnings,
    }
