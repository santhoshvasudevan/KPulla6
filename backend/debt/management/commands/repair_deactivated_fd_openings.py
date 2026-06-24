"""One-time repair for FDs deactivated before FD-ACC-10A cancel workflow."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from debt.models import FixedDeposit
from debt.repair_services import (
    DEFAULT_REPAIR_REASON,
    RepairEligibility,
    find_deactivated_fd_opening_repair_candidates,
    repair_deactivated_fd_opening,
)


class Command(BaseCommand):
    help = (
        "Identify and repair deactivated ledger-backed fixed deposits that still have "
        "an unreversed FD_OPENING bank debit. Dry-run by default; pass --apply to write."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Perform repairs (default: report candidates only).",
        )
        parser.add_argument(
            "--fd-id",
            type=int,
            help="Limit to a single fixed deposit id.",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            help="Limit to fixed deposits for a single user id.",
        )
        parser.add_argument(
            "--reason",
            default=DEFAULT_REPAIR_REASON,
            help="Audit reason stored on the FD_OPENING_REVERSAL movement.",
        )

    def handle(self, *args, **options):
        fd_id = options.get("fd_id")
        user_id = options.get("user_id")
        reason = (options.get("reason") or DEFAULT_REPAIR_REASON).strip()
        apply_changes = bool(options.get("apply"))

        if fd_id is not None:
            if not FixedDeposit.objects.filter(pk=fd_id).exists():
                raise CommandError(f"Fixed deposit {fd_id} not found.")

        reports = find_deactivated_fd_opening_repair_candidates(
            fd_id=fd_id,
            user_id=user_id,
        )

        eligible = [r for r in reports if r.eligibility == RepairEligibility.ELIGIBLE]
        skipped = [r for r in reports if r.eligibility == RepairEligibility.SKIP]

        if not reports:
            self.stdout.write("No inactive fixed deposits matched the query filters.")
            return

        self.stdout.write(
            f"Scanned {len(reports)} inactive fixed deposit(s): "
            f"{len(eligible)} eligible, {len(skipped)} skipped."
        )

        for report in reports:
            self._print_report(report)

        if not eligible:
            self.stdout.write(self.style.WARNING("No eligible repair candidates."))
            return

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run only — no changes made. Re-run with --apply to repair."
                )
            )
            return

        repaired = 0
        for report in eligible:
            fd = FixedDeposit.objects.select_related("user").get(pk=report.fixed_deposit_id)
            try:
                result = repair_deactivated_fd_opening(fd, reason=reason)
            except ValueError as exc:
                self.stdout.write(
                    self.style.ERROR(
                        f"FD {report.fixed_deposit_id}: skipped during apply — {exc}"
                    )
                )
                continue
            repaired += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"FD {result.fixed_deposit_id}: repaired — "
                    f"reversal movement {result.reversal_cash_movement_id}, "
                    f"status={result.status}, is_active={result.is_active}"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Repaired {repaired} fixed deposit(s)."))

    def _print_report(self, report) -> None:
        header = f"FD {report.fixed_deposit_id} — {report.institution_name}/{report.deposit_account_number}"
        if report.eligibility == RepairEligibility.ELIGIBLE:
            self.stdout.write(self.style.NOTICE(f"\n{header} [ELIGIBLE]"))
        else:
            self.stdout.write(self.style.WARNING(f"\n{header} [SKIP]"))

        self.stdout.write(f"  user_id: {report.user_id}")
        self.stdout.write(
            f"  portfolio: {report.portfolio_name} (id={report.portfolio_id})"
        )
        self.stdout.write(
            f"  bank account: {report.bank_account_name} (id={report.bank_account_id})"
        )
        self.stdout.write(f"  principal: {report.principal_amount}")
        self.stdout.write(f"  status: {report.status}; is_active: {report.is_active}")
        if report.opening_movement_id:
            self.stdout.write(
                f"  FD_OPENING: id={report.opening_movement_id}, "
                f"amount={report.opening_amount}, date={report.opening_date}"
            )
        else:
            self.stdout.write("  FD_OPENING: none (unreversed)")
        flags = []
        if report.has_interest_payments:
            flags.append("interest")
        if report.has_settlement:
            flags.append("settlement")
        if report.has_renewal:
            flags.append("renewal")
        self.stdout.write(f"  related records: {', '.join(flags) if flags else 'none'}")
        if report.skip_reason:
            self.stdout.write(f"  skip reason: {report.skip_reason}")
        if report.proposed_action:
            self.stdout.write(f"  proposed action: {report.proposed_action}")
