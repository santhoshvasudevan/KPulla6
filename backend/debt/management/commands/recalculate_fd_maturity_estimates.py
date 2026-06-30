"""Backfill FD maturity estimate fields without changing settlement accounting."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from debt.fd_maturity_services import _apply_estimate_fields
from debt.models import FixedDeposit, MaturityValueSource
from finance.fixed_deposits import is_payout_fd


class Command(BaseCommand):
    help = (
        "Recalculate stored FD maturity estimate fields for legacy rows. "
        "Default is dry-run; pass --apply to persist. Does not change ledger "
        "or settlement behavior; never overwrites USER_CONFIRMED expected values."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist changes (default: dry-run only).",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            help="Limit to a single user id.",
        )
        parser.add_argument(
            "--fd-id",
            type=int,
            help="Limit to a single fixed deposit id.",
        )

    def handle(self, *args, **options):
        dry_run = not options["apply"]
        qs = FixedDeposit.objects.all().order_by("id")
        if options["user_id"]:
            qs = qs.filter(user_id=options["user_id"])
        if options["fd_id"]:
            qs = qs.filter(pk=options["fd_id"])

        mode = "DRY-RUN" if dry_run else "APPLY"
        self.stdout.write(f"{mode}: scanning {qs.count()} fixed deposit(s)")

        updated = 0
        skipped = 0

        for fd in qs.iterator():
            before = (
                fd.estimated_maturity_value,
                fd.expected_maturity_value,
                fd.maturity_value_source,
                fd.maturity_estimate_method,
            )
            user_confirmed = fd.maturity_value_source == MaturityValueSource.USER_CONFIRMED

            _apply_estimate_fields(fd)
            if user_confirmed:
                # Preserve user-confirmed expected value; only fill missing estimate metadata.
                pass
            else:
                if fd.estimated_maturity_value is not None:
                    fd.expected_maturity_value = fd.estimated_maturity_value
                    if is_payout_fd(fd):
                        fd.maturity_value_source = MaturityValueSource.AUTO_PRINCIPAL
                    else:
                        fd.maturity_value_source = MaturityValueSource.AUTO_ESTIMATE
                else:
                    fd.expected_maturity_value = None
                    fd.maturity_value_source = MaturityValueSource.AUTO_ESTIMATE

            after = (
                fd.estimated_maturity_value,
                fd.expected_maturity_value,
                fd.maturity_value_source,
                fd.maturity_estimate_method,
            )
            if before == after:
                skipped += 1
                continue

            updated += 1
            self.stdout.write(
                f"  FD #{fd.id} {fd.institution_name} "
                f"principal={fd.principal_amount} {fd.currency} "
                f"estimate {before[0]} -> {after[0]} "
                f"expected {before[1]} -> {after[1]} "
                f"source {before[2]} -> {after[2]}"
            )

            if not dry_run:
                with transaction.atomic():
                    fd.save(
                        update_fields=[
                            "estimated_maturity_value",
                            "expected_maturity_value",
                            "maturity_value_source",
                            "maturity_estimate_method",
                            "updated_at",
                        ]
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} complete: {updated} would update, {skipped} unchanged"
            )
        )
        if dry_run and updated:
            self.stdout.write("Re-run with --apply to persist estimate fields.")
