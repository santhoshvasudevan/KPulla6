"""Backfill missing BUY/SELL settlement rows for cash-aware portfolios."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from portfolios.models import Portfolio
from transactions.cash_settlement_sync import (
    CashSettlementSyncBlockedError,
    CashSettlementSyncError,
    apply_cash_settlement_sync,
    plan_cash_settlement_sync,
    plan_to_dict,
    validate_plan_negative_cash,
)


class Command(BaseCommand):
    help = (
        "Backfill missing BUY/SELL settlement rows for one cash-aware portfolio. "
        "Dry-run by default; pass --apply to write rows."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--portfolio-id",
            type=int,
            required=True,
            help="Portfolio to sync (one portfolio per run).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Create missing settlement rows (default: dry-run report only).",
        )
        parser.add_argument(
            "--allow-legacy",
            action="store_true",
            help="Allow sync when cash_aware_enabled=false (normally rejected).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit machine-readable JSON report.",
        )

    def handle(self, *args, **options):
        portfolio_id = options["portfolio_id"]
        try:
            portfolio = Portfolio.objects.get(pk=portfolio_id)
        except Portfolio.DoesNotExist as exc:
            raise CommandError(f"Portfolio {portfolio_id} not found.") from exc

        if not portfolio.cash_aware_enabled and not options["allow_legacy"]:
            raise CommandError(
                f"Portfolio {portfolio_id} is not cash-aware. "
                "Enable cash_aware_enabled or pass --allow-legacy."
            )

        plan = plan_cash_settlement_sync(portfolio)
        negative_impacts = validate_plan_negative_cash(portfolio, plan)
        report = plan_to_dict(plan)
        report["negative_cash_impacts"] = negative_impacts
        report["apply_allowed"] = (
            plan.create_count > 0
            and not plan.mismatches
            and not negative_impacts
        )

        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2, default=str))
        else:
            self._print_report(plan, negative_impacts)

        if not options["apply"]:
            if plan.create_count:
                self.stdout.write(
                    self.style.WARNING(
                        f"Dry-run: would create {plan.create_count} settlement row(s). "
                        "Re-run with --apply after backup."
                    )
                )
            return

        if plan.mismatches:
            raise CommandError(
                f"Apply blocked: {len(plan.mismatches)} mismatch(es). "
                "Resolve mismatches before applying."
            )
        if negative_impacts:
            raise CommandError(
                "Apply blocked: historical cash would go negative. "
                "Add deposits first — see negative_cash_impacts in report."
            )
        if plan.create_count == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to apply — already synced."))
            return

        try:
            result = apply_cash_settlement_sync(portfolio)
        except CashSettlementSyncBlockedError as exc:
            raise CommandError(str(exc)) from exc
        except CashSettlementSyncError as exc:
            raise CommandError(str(exc)) from exc

        msg = (
            f"Created {result['created_count']} settlement row(s) "
            f"for portfolio {portfolio_id}."
        )
        self.stdout.write(self.style.SUCCESS(msg))

    def _print_report(self, plan, negative_impacts) -> None:
        self.stdout.write("=== Cash settlement sync ===")
        self.stdout.write(
            f"  portfolio_id={plan.portfolio_id} "
            f"name={plan.portfolio_name!r} "
            f"cash_aware={plan.cash_aware_enabled}"
        )
        self.stdout.write(f"  to_create: {plan.create_count}")
        self.stdout.write(f"  already_synced: {plan.already_synced}")
        self.stdout.write(f"  mismatches: {len(plan.mismatches)}")
        self.stdout.write(f"  skipped_non_settlement: {plan.skipped_non_settlement}")

        if plan.to_create:
            self.stdout.write("\n=== Planned settlements ===")
            for item in plan.to_create[:20]:
                self.stdout.write(
                    f"  txn={item.transaction_id} {item.transaction_type} "
                    f"{item.asset_symbol} {item.entry_type} "
                    f"{item.amount} {item.currency} date={item.ledger_date}"
                )
            if plan.create_count > 20:
                self.stdout.write(f"  ... and {plan.create_count - 20} more")

        if plan.mismatches:
            self.stdout.write("\n=== Mismatches (not auto-fixed) ===")
            for m in plan.mismatches:
                self.stdout.write(
                    f"  txn={m.transaction_id} settlement={m.settlement_id} "
                    f"[{m.code}] {m.detail}"
                )

        if negative_impacts:
            self.stdout.write("\n=== Negative cash would result ===")
            for impact in negative_impacts:
                self.stdout.write(f"  {impact}")
