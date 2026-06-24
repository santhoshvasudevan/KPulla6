"""Infer BankAccount.portfolio from linked FDs and cash movements (CASH-UNIFY-1)."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from debt.bank_account_portfolio import (
    InferenceOutcome,
    apply_bank_account_portfolio_inference,
    find_bank_account_inference_reports,
)
from debt.models import BankAccount


class Command(BaseCommand):
    help = (
        "Infer nullable BankAccount.portfolio from unambiguous fixed-deposit and "
        "cash-movement signals. Dry-run by default; pass --apply to write."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Assign portfolio on unambiguous bank accounts (default: report only).",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            help="Limit to bank accounts for a single user id.",
        )
        parser.add_argument(
            "--bank-account-id",
            type=int,
            help="Limit to a single bank account id.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help=(
                "When set with --apply, skip accounts that already have portfolio "
                "assigned (default behavior without --strict is also skip assigned)."
            ),
        )

    def handle(self, *args, **options):
        user_id = options.get("user_id")
        bank_account_id = options.get("bank_account_id")
        apply_changes = bool(options.get("apply"))
        strict = bool(options.get("strict"))

        if bank_account_id is not None:
            if not BankAccount.objects.filter(pk=bank_account_id).exists():
                raise CommandError(f"Bank account {bank_account_id} not found.")

        reports = find_bank_account_inference_reports(
            user_id=user_id,
            bank_account_id=bank_account_id,
        )

        if not reports:
            self.stdout.write("No active bank accounts matched the query filters.")
            return

        counts = {outcome: 0 for outcome in InferenceOutcome}
        for report in reports:
            counts[report.outcome] += 1
            self._print_report(report)

        self.stdout.write(
            "\nSummary: "
            f"inferred={counts[InferenceOutcome.INFERRED]}, "
            f"ambiguous={counts[InferenceOutcome.AMBIGUOUS]}, "
            f"unassigned={counts[InferenceOutcome.UNASSIGNED]}, "
            f"unchanged={counts[InferenceOutcome.UNCHANGED]}, "
            f"skipped={counts[InferenceOutcome.SKIPPED]}"
        )

        candidates = [
            r for r in reports if r.outcome == InferenceOutcome.INFERRED
        ]
        if not candidates:
            self.stdout.write(self.style.WARNING("No unambiguous inference candidates."))
            return

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run only — no changes made. Re-run with --apply to assign."
                )
            )
            return

        assigned = 0
        for report in candidates:
            account = BankAccount.objects.select_related("user").get(
                pk=report.bank_account_id
            )
            if account.portfolio_id and strict:
                self.stdout.write(
                    self.style.WARNING(
                        f"Bank account {account.id}: skipped (--strict, already assigned)."
                    )
                )
                continue
            if account.portfolio_id:
                self.stdout.write(
                    f"Bank account {account.id}: skipped (portfolio already assigned)."
                )
                continue
            assert report.inferred_portfolio_id is not None
            apply_bank_account_portfolio_inference(
                account, portfolio_id=report.inferred_portfolio_id
            )
            assigned += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Bank account {account.id}: assigned portfolio "
                    f"{report.inferred_portfolio_id}."
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Assigned portfolio on {assigned} account(s)."))

    def _print_report(self, report) -> None:
        label = report.outcome.value.upper()
        style = {
            InferenceOutcome.INFERRED: self.style.NOTICE,
            InferenceOutcome.AMBIGUOUS: self.style.WARNING,
            InferenceOutcome.UNASSIGNED: self.style.WARNING,
            InferenceOutcome.UNCHANGED: self.style.HTTP_INFO,
            InferenceOutcome.SKIPPED: self.style.HTTP_INFO,
        }.get(report.outcome, self.style.NOTICE)
        self.stdout.write(
            style(
                f"\nBank account {report.bank_account_id} ({report.account_name}) [{label}]"
            )
        )
        self.stdout.write(f"  user_id: {report.user_id}")
        self.stdout.write(f"  current_portfolio_id: {report.current_portfolio_id}")
        self.stdout.write(
            f"  associated_portfolio_ids: {sorted(report.associated_portfolio_ids)}"
        )
        self.stdout.write(f"  inferred_portfolio_id: {report.inferred_portfolio_id}")
        self.stdout.write(f"  detail: {report.detail}")
