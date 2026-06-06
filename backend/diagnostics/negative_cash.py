"""Negative cash balance diagnostics (read-only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from cash.services import ledger_entries_queryset, ledger_entry_to_point
from finance.cash import cash_balance_timeseries
from portfolios.models import Portfolio


@dataclass(frozen=True)
class NegativeCashIssue:
    portfolio_id: int
    portfolio_name: str
    currency: str
    earliest_negative_date: date
    lowest_balance: Decimal
    triggering_entry_id: int | None
    triggering_entry_date: date | None
    triggering_entry_type: str | None
    triggering_entry_amount: Decimal | None


def _scan_portfolio_currency(
    portfolio: Portfolio,
    currency: str,
) -> NegativeCashIssue | None:
    rows = list(ledger_entries_queryset(portfolio, currency=currency))
    if not rows:
        return None

    points = [ledger_entry_to_point(row) for row in rows]
    start = min(row.date for row in rows)
    end = max(row.date for row in rows)
    series = cash_balance_timeseries(points, start, end).get(currency, [])
    if not series:
        return None

    earliest_negative: date | None = None
    lowest = Decimal("0")
    for day, balance in series:
        if balance < lowest:
            lowest = balance
        if balance < 0 and earliest_negative is None:
            earliest_negative = day

    if earliest_negative is None:
        return None

    pre_balance = sum(
        (row.amount for row in rows if row.date < earliest_negative),
        Decimal("0"),
    )
    trigger_row = None
    running = pre_balance
    for row in sorted(
        (r for r in rows if r.date == earliest_negative),
        key=lambda r: r.id,
    ):
        before = running
        running += row.amount
        if running < 0 and before >= 0:
            trigger_row = row
            break
    if trigger_row is None:
        day_rows = [r for r in rows if r.date == earliest_negative]
        trigger_row = day_rows[-1] if day_rows else None

    return NegativeCashIssue(
        portfolio_id=portfolio.id,
        portfolio_name=portfolio.name,
        currency=currency,
        earliest_negative_date=earliest_negative,
        lowest_balance=lowest,
        triggering_entry_id=trigger_row.id if trigger_row else None,
        triggering_entry_date=trigger_row.date if trigger_row else None,
        triggering_entry_type=trigger_row.entry_type if trigger_row else None,
        triggering_entry_amount=trigger_row.amount if trigger_row else None,
    )


def check_negative_cash(
    portfolios: list[Portfolio],
    *,
    currency_filter: str | None = None,
) -> list[NegativeCashIssue]:
    issues: list[NegativeCashIssue] = []
    ccy_filter = currency_filter.upper() if currency_filter else None

    for portfolio in portfolios:
        currencies = set(
            ledger_entries_queryset(portfolio).values_list("currency", flat=True)
        )
        if ccy_filter:
            currencies = {c for c in currencies if c == ccy_filter}
        for currency in sorted(currencies):
            issue = _scan_portfolio_currency(portfolio, currency)
            if issue is not None:
                issues.append(issue)
    return issues


def build_negative_cash_report(issues: list[NegativeCashIssue]) -> dict[str, Any]:
    return {
        "issue_count": len(issues),
        "issues": [asdict(i) for i in issues],
    }


def format_negative_cash_report(issues: list[NegativeCashIssue]) -> None:
    print("\n=== Summary ===")
    print(f"  negative_balance_cases: {len(issues)}")
    if not issues:
        print("\n(no negative running cash balances found)")
        return
    print("\n=== Issues ===")
    for issue in issues:
        print(
            f"  portfolio={issue.portfolio_id} ({issue.portfolio_name!r}) "
            f"{issue.currency}: earliest_negative={issue.earliest_negative_date} "
            f"lowest={issue.lowest_balance} "
            f"entry_id={issue.triggering_entry_id} "
            f"type={issue.triggering_entry_type} amount={issue.triggering_entry_amount}"
        )
