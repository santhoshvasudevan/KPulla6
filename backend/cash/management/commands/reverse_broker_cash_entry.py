"""Reverse a manual broker cash ledger entry (CASH-CORR-1A)."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from cash.models import CashLedgerEntry
from cash.reversal_services import (
    CashReversalValidationError,
    _opposite_signed_amount,
    broker_cash_balance_preview,
    is_reversible_manual_entry,
    reverse_broker_cash_ledger_entry,
)
from cash.services import CashValidationError, FutureCashImpactError, InsufficientCashError


class Command(BaseCommand):
    help = (
        "Reverse a manual broker CashLedgerEntry (CASH_DEPOSIT / CASH_WITHDRAWAL). "
        "Dry-run by default; pass --apply to write the reversal entry."
    )

    def add_arguments(self, parser):
        parser.add_argument("--entry-id", type=int, required=True)
        parser.add_argument("--reason", type=str, required=True)
        parser.add_argument("--reversal-date", type=str, default=None)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Create the reversal entry (default is dry-run preview only).",
        )
        parser.add_argument("--username", type=str, default=None)

    def handle(self, *args, **options):
        entry_id = options["entry_id"]
        reason = options["reason"]
        reversal_date = options.get("reversal_date")
        apply = options["apply"]
        username = options.get("username")

        User = get_user_model()
        entry = (
            CashLedgerEntry.objects.select_related("portfolio", "portfolio__user")
            .filter(pk=entry_id)
            .first()
        )
        if entry is None:
            raise CommandError(f"CashLedgerEntry {entry_id} not found.")

        user = entry.portfolio.user
        if username:
            user = User.objects.filter(username=username).first()
            if user is None:
                raise CommandError(f"User {username!r} not found.")
            if entry.portfolio.user_id != user.id:
                raise CommandError(
                    f"Entry {entry_id} does not belong to user {username!r}."
                )

        if not is_reversible_manual_entry(entry):
            raise CommandError(
                f"Entry {entry_id} is not eligible for reversal "
                f"(type={entry.entry_type}, is_reversal={entry.is_reversal})."
            )

        preview_balance = broker_cash_balance_preview(
            user, entry.portfolio_id, entry.currency
        )
        projected = {
            **preview_balance,
            "projected_balance": float(
                Decimal(str(preview_balance["current_balance"]))
                + _opposite_signed_amount(entry)
            ),
        }
        self.stdout.write(
            f"Entry #{entry.id}: {entry.entry_type} {entry.amount} {entry.currency} "
            f"portfolio={entry.portfolio.name!r} date={entry.date}"
        )
        self.stdout.write(
            f"Broker cash balance now: {projected['current_balance']} "
            f"{projected['currency']}"
        )
        self.stdout.write(
            f"Projected after reversal: {projected['projected_balance']} "
            f"{projected['currency']}"
        )
        self.stdout.write(f"Reason: {reason.strip()}")
        if reversal_date:
            self.stdout.write(f"Reversal date: {reversal_date}")

        if not apply:
            self.stdout.write(self.style.WARNING("Dry-run only — no changes written."))
            self.stdout.write("Re-run with --apply to create the reversal entry.")
            return

        try:
            result = reverse_broker_cash_ledger_entry(
                user,
                entry_id,
                reversal_date=reversal_date,
                reason=reason,
            )
        except (
            CashReversalValidationError,
            CashValidationError,
            InsufficientCashError,
            FutureCashImpactError,
        ) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Created reversal entry #{result.reversal.id} "
                f"({result.reversal.entry_type} {result.reversal.amount} "
                f"{result.reversal.currency} @ {result.reversal.date})."
            )
        )
