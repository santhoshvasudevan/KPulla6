"""Read-only audit of recorded FD renewals for proceeds and ledger discrepancies (#44)."""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from debt.renewal_audit_services import (
    audit_fixed_deposit_renewals,
    renewal_audit_report_to_dict,
)
from finance.fd_renewal_audit import (
    STATUS_CONSISTENT,
    STATUS_INCOMPLETE,
    STATUS_INCONSISTENT,
)


class Command(BaseCommand):
    help = (
        "Audit recorded fixed deposit renewals against the direct-renewal rules: "
        "principal, final net interest, reinvested principal, cash payout, and linked "
        "bank credits. Read-only — never repairs or writes data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="Limit to renewals for a single user id (default: all users).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the full audit report as JSON.",
        )

    def handle(self, *args, **options):
        user_id = options.get("user_id")
        if user_id is not None and not get_user_model().objects.filter(pk=user_id).exists():
            raise CommandError(f"User {user_id} not found.")

        # The audit only reads; the rolled-back transaction guarantees nothing persists.
        with transaction.atomic():
            report = audit_fixed_deposit_renewals(user_id=user_id)
            transaction.set_rollback(True)

        if options.get("json"):
            self.stdout.write(json.dumps(renewal_audit_report_to_dict(report), indent=2))
            return
        self._print_text(report)

    def _print_text(self, report) -> None:
        summary = report.summary
        if not report.results:
            self.stdout.write("No fixed deposit renewals matched the query filters.")
            return

        for result in report.results:
            self._print_result(result)

        counts = summary.status_counts
        self.stdout.write(
            f"\nAudited {summary.renewal_count} renewal(s): "
            f"{counts[STATUS_CONSISTENT]} consistent, "
            f"{counts[STATUS_INCONSISTENT]} inconsistent, "
            f"{counts[STATUS_INCOMPLETE]} incomplete."
        )
        for totals in summary.totals_by_currency:
            self.stdout.write(
                f"  {totals.currency}: old principal {totals.old_principal:,.2f}; "
                f"final net interest {totals.net_interest:,.2f}; "
                f"reinvested {totals.reinvested_principal:,.2f}; "
                f"cash payout recorded {totals.cash_payout_recorded:,.2f}; "
                f"linked bank credits {totals.ledger_payout_total:,.2f}; "
                f"confirmed later payouts {totals.confirmed_later_payout_net:,.2f}; "
                f"pending estimates (not settled) {totals.pending_estimate_net:,.2f}"
            )
        if summary.finding_counts:
            self.stdout.write("Findings:")
        for code, count in summary.finding_counts.items():
            self.stdout.write(f"  {code}: {count}")
        self.stdout.write(
            self.style.WARNING("Read-only audit — no records were changed.")
        )

    def _print_result(self, result) -> None:
        old, new = result.old_term, result.new_term
        header = (
            f"Renewal {result.renewal_id} on {result.renewal_date} — "
            f"{old.institution_name}/{old.deposit_account_number} (FD {old.id}) → "
            f"{new.deposit_account_number} (FD {new.id}) [{result.status}]"
        )
        if result.status == STATUS_CONSISTENT:
            self.stdout.write(self.style.SUCCESS(f"\n{header}"))
        elif result.status == STATUS_INCONSISTENT:
            self.stdout.write(self.style.ERROR(f"\n{header}"))
        else:
            self.stdout.write(self.style.WARNING(f"\n{header}"))

        t, c = result.totals, result.currency
        self.stdout.write(
            f"  available: old principal {t.old_principal:,.2f} + final net interest "
            f"{t.net_interest:,.2f} (gross {t.gross_interest:,.2f}, tax "
            f"{t.tax_withheld:,.2f}) = {c} {t.total_available:,.2f}"
        )
        self.stdout.write(
            f"  allocated: reinvested {t.reinvested_principal:,.2f} + cash payout "
            f"{t.cash_payout_recorded:,.2f} (gap {t.allocation_gap:,.2f})"
        )
        self.stdout.write(
            f"  bank credits: settlement {t.ledger_payout_total:,.2f} "
            f"(interest {t.ledger_interest_total:,.2f}, principal "
            f"{t.ledger_principal_total:,.2f}) movements "
            f"{list(result.settlement_movement_ids) or 'none'}; "
            f"unlinked {t.unlinked_movement_total:,.2f}"
        )
        if result.pending_payout_id is not None:
            self.stdout.write(
                f"  final payout #{result.pending_payout_id}: pending estimate "
                f"{t.pending_estimate_net:,.2f} (not settled), confirmed "
                f"{t.confirmed_later_payout_net:,.2f}"
            )
        for finding in result.findings:
            self.stdout.write(f"  - {finding.kind} {finding.code}: {finding.message}")
