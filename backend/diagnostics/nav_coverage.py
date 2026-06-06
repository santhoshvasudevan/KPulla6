"""Mutual fund NAV coverage diagnostics (read-only; DB cache only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from finance.fifo import calculate_fifo_cost_basis_metrics
from market_data.nav_lookup import normalize_scheme_code
from market_data.nav_repository import (
    latest_mutual_fund_navs_by_scheme,
    list_mutual_fund_navs_in_range,
)
from portfolios import dates as portfolio_dates
from portfolios.summary_service import fifo_eligible_queryset, transactions_by_mf_holding
from transactions.finance_adapter import transaction_to_finance_dto
from transactions.models import Transaction, TransactionType


@dataclass(frozen=True)
class NavCoverageIssue:
    scheme_code: str
    portfolio_id: int
    code: str
    first_transaction_date: date | None
    latest_nav_date: date | None
    stale_days: int | None
    detail: str


def _held_schemes_by_portfolio(
    portfolio_ids: list[int],
) -> dict[int, dict[str, tuple[date, list[Transaction]]]]:
    """portfolio_id -> scheme -> (first_date, txns). Only schemes with open units."""
    queryset = fifo_eligible_queryset(portfolio_ids)
    by_mf = transactions_by_mf_holding(queryset)
    out: dict[int, dict[str, tuple[date, list[Transaction]]]] = {}

    for _key, txns in by_mf.items():
        if not txns:
            continue
        scheme = normalize_scheme_code(txns[0].asset_symbol)
        portfolio_id = txns[0].portfolio_id
        fifo_txns = [
            transaction_to_finance_dto(t)
            for t in txns
            if t.type in {TransactionType.BUY.value, TransactionType.SELL.value}
        ]
        metrics = calculate_fifo_cost_basis_metrics(fifo_txns, current_price=Decimal("1"))
        if metrics.cumulative_qty <= 0:
            continue
        first_date = min(t.mutual_fund_detail.investment_date for t in txns)
        out.setdefault(portfolio_id, {})[scheme] = (first_date, txns)
    return out


def check_nav_coverage(
    portfolio_ids: list[int],
    *,
    stale_days: int = 5,
    today: date | None = None,
) -> list[NavCoverageIssue]:
    as_of = today or portfolio_dates.current_date()
    held = _held_schemes_by_portfolio(portfolio_ids)
    all_schemes = sorted({s for schemes in held.values() for s in schemes})
    latest_navs = latest_mutual_fund_navs_by_scheme(all_schemes)
    issues: list[NavCoverageIssue] = []

    for portfolio_id, schemes in held.items():
        for scheme, (first_date, _txns) in schemes.items():
            nav_result = latest_navs.get(scheme)
            latest_date = nav_result.date if nav_result and nav_result.date else None
            latest_nav = nav_result.nav if nav_result else None

            if latest_date is None or latest_nav is None:
                issues.append(
                    NavCoverageIssue(
                        scheme_code=scheme,
                        portfolio_id=portfolio_id,
                        code="missing_latest_nav",
                        first_transaction_date=first_date,
                        latest_nav_date=latest_date,
                        stale_days=None,
                        detail="No cached latest NAV for held scheme",
                    )
                )
                continue

            if latest_date < first_date:
                issues.append(
                    NavCoverageIssue(
                        scheme_code=scheme,
                        portfolio_id=portfolio_id,
                        code="nav_before_first_transaction",
                        first_transaction_date=first_date,
                        latest_nav_date=latest_date,
                        stale_days=None,
                        detail=(
                            f"Latest NAV date {latest_date} is before first txn {first_date}"
                        ),
                    )
                )

            gap_start = first_date
            gap_end = min(as_of, latest_date)
            if gap_end >= gap_start:
                rows = list_mutual_fund_navs_in_range(scheme, gap_start, gap_end)
                row_dates = {r.date for r in rows}
                probe = gap_start
                missing_after: date | None = None
                while probe <= gap_end:
                    if probe not in row_dates:
                        on_or_before = [r for r in rows if r.date <= probe]
                        if not on_or_before and probe == gap_start:
                            missing_after = probe
                            break
                    probe += timedelta(days=1)
                if missing_after is not None and missing_after > first_date:
                    issues.append(
                        NavCoverageIssue(
                            scheme_code=scheme,
                            portfolio_id=portfolio_id,
                            code="missing_nav_after_transaction",
                            first_transaction_date=first_date,
                            latest_nav_date=latest_date,
                            stale_days=None,
                            detail=(
                                f"No NAV row on or before {missing_after} after first txn"
                            ),
                        )
                    )

            age = (as_of - latest_date).days
            if age > stale_days:
                issues.append(
                    NavCoverageIssue(
                        scheme_code=scheme,
                        portfolio_id=portfolio_id,
                        code="stale_nav",
                        first_transaction_date=first_date,
                        latest_nav_date=latest_date,
                        stale_days=age,
                        detail=(
                            f"Latest NAV is {age} days old (threshold {stale_days})"
                        ),
                    )
                )

    return issues


def build_nav_coverage_report(
    issues: list[NavCoverageIssue],
    *,
    stale_days: int,
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.code] = counts.get(issue.code, 0) + 1
    return {
        "stale_days_threshold": stale_days,
        "issue_count": len(issues),
        "issue_counts_by_code": counts,
        "issues": [asdict(i) for i in issues],
    }


def format_nav_coverage_report(issues: list[NavCoverageIssue]) -> None:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.code] = counts.get(issue.code, 0) + 1
    print("\n=== Summary ===")
    print(f"  total_issues: {len(issues)}")
    if counts:
        print("  by_code:")
        for code, n in sorted(counts.items()):
            print(f"    {code}: {n}")
    if not issues:
        print("\n(no MF NAV coverage issues found for held schemes)")
        return
    print("\n=== Issues ===")
    for issue in issues:
        print(
            f"  [{issue.code}] portfolio={issue.portfolio_id} scheme={issue.scheme_code} "
            f"first_txn={issue.first_transaction_date} latest_nav={issue.latest_nav_date}: "
            f"{issue.detail}"
        )
