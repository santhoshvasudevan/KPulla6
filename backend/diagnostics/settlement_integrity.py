"""Settlement ledger integrity checks (read-only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Count

from cash.models import CashEntryType, CashLedgerEntry
from cash.services import is_manual_editable_entry
from portfolios.models import Portfolio
from transactions.cash_settlement import _mf_settlement_spec, _stock_settlement_spec
from transactions.models import MutualFundTransactionDetail, Transaction, TransactionType


@dataclass(frozen=True)
class SettlementIssue:
    code: str
    portfolio_id: int
    transaction_id: int | None
    settlement_id: int | None
    detail: str


def _issue_counts(issues: list[SettlementIssue]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.code] = counts.get(issue.code, 0) + 1
    return counts


def _expected_settlement(txn: Transaction) -> tuple[str | None, Decimal | None, object | None]:
    """Return (entry_type, amount, ledger_date) from production settlement rules."""
    if txn.type in {TransactionType.STOCK_SPLIT, TransactionType.DIVIDEND}:
        return None, None, None
    try:
        detail = txn.mutual_fund_detail
    except MutualFundTransactionDetail.DoesNotExist:
        detail = None
    if detail is not None:
        spec = _mf_settlement_spec(txn, detail)
    else:
        spec = _stock_settlement_spec(txn)
    return spec.entry_type, spec.amount, spec.ledger_date


def check_settlement_integrity(
    portfolios: list[Portfolio],
) -> list[SettlementIssue]:
    issues: list[SettlementIssue] = []
    portfolio_ids = [p.id for p in portfolios]
    cash_aware_ids = {p.id for p in portfolios if p.cash_aware_enabled}

    settlements = (
        CashLedgerEntry.objects.filter(
            portfolio_id__in=portfolio_ids,
            entry_type__in=(
                CashEntryType.BUY_SETTLEMENT,
                CashEntryType.SELL_SETTLEMENT,
            ),
        )
        .select_related("linked_transaction", "portfolio")
        .order_by("portfolio_id", "linked_transaction_id", "id")
    )
    settlements_by_txn: dict[int, list[CashLedgerEntry]] = {}
    for entry in settlements:
        if entry.linked_transaction_id is None:
            issues.append(
                SettlementIssue(
                    code="orphan_settlement_no_transaction",
                    portfolio_id=entry.portfolio_id,
                    transaction_id=None,
                    settlement_id=entry.id,
                    detail=f"{entry.entry_type} row has no linked_transaction_id",
                )
            )
            continue
        if entry.linked_transaction is None:
            issues.append(
                SettlementIssue(
                    code="settlement_missing_transaction",
                    portfolio_id=entry.portfolio_id,
                    transaction_id=entry.linked_transaction_id,
                    settlement_id=entry.id,
                    detail="linked transaction row is missing",
                )
            )
            continue
        settlements_by_txn.setdefault(entry.linked_transaction_id, []).append(entry)

    txns = (
        Transaction.objects.filter(portfolio_id__in=portfolio_ids)
        .select_related("mutual_fund_detail")
        .order_by("portfolio_id", "id")
    )

    for txn in txns:
        linked = settlements_by_txn.get(txn.id, [])
        expected_type, expected_amount, expected_date = _expected_settlement(txn)

        if txn.type == TransactionType.STOCK_SPLIT and linked:
            issues.append(
                SettlementIssue(
                    code="split_has_settlement",
                    portfolio_id=txn.portfolio_id,
                    transaction_id=txn.id,
                    settlement_id=linked[0].id,
                    detail="STOCK_SPLIT must not have a settlement row",
                )
            )
            continue

        if txn.portfolio_id in cash_aware_ids and txn.type in (
            TransactionType.BUY,
            TransactionType.SELL,
        ):
            if expected_type is not None and not linked:
                issues.append(
                    SettlementIssue(
                        code="missing_settlement",
                        portfolio_id=txn.portfolio_id,
                        transaction_id=txn.id,
                        settlement_id=None,
                        detail=f"cash-aware {txn.type} has no linked settlement",
                    )
                )
        elif linked and txn.portfolio_id not in cash_aware_ids:
            issues.append(
                SettlementIssue(
                    code="legacy_portfolio_has_settlement",
                    portfolio_id=txn.portfolio_id,
                    transaction_id=txn.id,
                    settlement_id=linked[0].id,
                    detail="legacy portfolio (cash_aware_enabled=false) has settlement row",
                )
            )

        if len(linked) > 1:
            issues.append(
                SettlementIssue(
                    code="duplicate_settlement",
                    portfolio_id=txn.portfolio_id,
                    transaction_id=txn.id,
                    settlement_id=linked[1].id,
                    detail=f"{len(linked)} settlement rows for one transaction",
                )
            )

        for entry in linked:
            if entry.portfolio_id != txn.portfolio_id:
                issues.append(
                    SettlementIssue(
                        code="settlement_portfolio_mismatch",
                        portfolio_id=txn.portfolio_id,
                        transaction_id=txn.id,
                        settlement_id=entry.id,
                        detail=(
                            f"settlement portfolio_id={entry.portfolio_id} "
                            f"!= transaction portfolio_id={txn.portfolio_id}"
                        ),
                    )
                )

            if is_manual_editable_entry(entry):
                issues.append(
                    SettlementIssue(
                        code="settlement_marked_manual_editable",
                        portfolio_id=txn.portfolio_id,
                        transaction_id=txn.id,
                        settlement_id=entry.id,
                        detail="system settlement row passes manual-editable check unexpectedly",
                    )
                )

            if expected_type is None:
                if entry.entry_type in (
                    CashEntryType.BUY_SETTLEMENT,
                    CashEntryType.SELL_SETTLEMENT,
                ):
                    issues.append(
                        SettlementIssue(
                            code="unexpected_settlement_type",
                            portfolio_id=txn.portfolio_id,
                            transaction_id=txn.id,
                            settlement_id=entry.id,
                            detail=f"{txn.type} should not have settlement",
                        )
                    )
                continue

            if entry.entry_type != expected_type:
                issues.append(
                    SettlementIssue(
                        code="settlement_type_mismatch",
                        portfolio_id=txn.portfolio_id,
                        transaction_id=txn.id,
                        settlement_id=entry.id,
                        detail=f"expected {expected_type}, got {entry.entry_type}",
                    )
                )

            if expected_amount is not None and entry.amount != expected_amount:
                issues.append(
                    SettlementIssue(
                        code="settlement_amount_mismatch",
                        portfolio_id=txn.portfolio_id,
                        transaction_id=txn.id,
                        settlement_id=entry.id,
                        detail=(
                            f"expected amount {expected_amount}, got {entry.amount}"
                        ),
                    )
                )

            if expected_date is not None and entry.date != expected_date:
                issues.append(
                    SettlementIssue(
                        code="settlement_date_mismatch",
                        portfolio_id=txn.portfolio_id,
                        transaction_id=txn.id,
                        settlement_id=entry.id,
                        detail=(
                            f"expected ledger date {expected_date}, got {entry.date}"
                        ),
                    )
                )

            try:
                detail = txn.mutual_fund_detail
            except MutualFundTransactionDetail.DoesNotExist:
                detail = None
            if detail is not None and entry.date != detail.investment_date:
                issues.append(
                    SettlementIssue(
                        code="mf_settlement_not_on_investment_date",
                        portfolio_id=txn.portfolio_id,
                        transaction_id=txn.id,
                        settlement_id=entry.id,
                        detail=(
                            f"MF settlement date {entry.date} != "
                            f"investment_date {detail.investment_date}"
                        ),
                    )
                )

    dup_qs = (
        CashLedgerEntry.objects.filter(
            portfolio_id__in=portfolio_ids,
            linked_transaction_id__isnull=False,
            entry_type__in=(
                CashEntryType.BUY_SETTLEMENT,
                CashEntryType.SELL_SETTLEMENT,
            ),
        )
        .values("linked_transaction_id")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )
    for row in dup_qs:
        txn_id = row["linked_transaction_id"]
        if any(i.code == "duplicate_settlement" and i.transaction_id == txn_id for i in issues):
            continue
        extras = settlements_by_txn.get(txn_id, [])[1:]
        for entry in extras:
            issues.append(
                SettlementIssue(
                    code="duplicate_settlement",
                    portfolio_id=entry.portfolio_id,
                    transaction_id=txn_id,
                    settlement_id=entry.id,
                    detail="duplicate settlement row detected via aggregate",
                )
            )

    return issues


def build_settlement_report(
    portfolios: list[Portfolio],
    issues: list[SettlementIssue],
) -> dict[str, Any]:
    return {
        "portfolios_checked": len(portfolios),
        "issue_count": len(issues),
        "issue_counts_by_code": _issue_counts(issues),
        "issues": [asdict(i) for i in issues],
    }


def format_settlement_report(issues: list[SettlementIssue]) -> None:
    counts = _issue_counts(issues)
    print("\n=== Summary ===")
    print(f"  total_issues: {len(issues)}")
    if counts:
        print("  by_code:")
        for code, n in sorted(counts.items()):
            print(f"    {code}: {n}")
    if not issues:
        print("\n(no settlement integrity issues found)")
        return
    print("\n=== Issues ===")
    for issue in issues:
        print(
            f"  [{issue.code}] portfolio={issue.portfolio_id} "
            f"txn={issue.transaction_id} settlement={issue.settlement_id}: "
            f"{issue.detail}"
        )
