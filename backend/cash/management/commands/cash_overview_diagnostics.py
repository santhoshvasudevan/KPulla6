"""Read-only cash overview diagnostics (CASH-UNIFY-4A)."""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from cash.diagnostics_service import build_cash_diagnostics, cash_diagnostics_to_dict
from portfolios.models import Portfolio


class Command(BaseCommand):
    help = (
        "Summarize broker/bank cash state for manual-data sanity checks. "
        "Read-only — no ledger or balance mutations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--portfolio-id",
            type=int,
            default=None,
            help="Optional portfolio scope filter.",
        )
        parser.add_argument(
            "--username",
            type=str,
            default=None,
            help="User to inspect (default: first user in DB).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit machine-readable JSON instead of human text.",
        )

    def handle(self, *args, **options):
        portfolio_id = options.get("portfolio_id")
        username = options.get("username")
        as_json = options.get("json")

        User = get_user_model()
        if username:
            user = User.objects.filter(username=username).first()
            if user is None:
                raise CommandError(f"User {username!r} not found.")
        else:
            user = User.objects.order_by("id").first()
            if user is None:
                raise CommandError("No users in database.")

        if portfolio_id is not None:
            portfolio = Portfolio.objects.filter(
                pk=portfolio_id, user=user, is_active=True
            ).first()
            if portfolio is None:
                raise CommandError(
                    f"Portfolio {portfolio_id} not found for user {user.username!r}."
                )

        result = build_cash_diagnostics(user, portfolio_id=portfolio_id)
        payload = cash_diagnostics_to_dict(result)

        if as_json:
            self.stdout.write(json.dumps(payload, indent=2))
            return

        self.stdout.write(f"Cash diagnostics for user={user.username!r}")
        if portfolio_id is not None:
            self.stdout.write(f"Portfolio scope: {portfolio_id}")
        self.stdout.write(f"As of: {payload['as_of_date']}")
        self.stdout.write("")

        self.stdout.write("Broker cash by portfolio/currency:")
        if payload["broker_cash_by_portfolio"]:
            for row in payload["broker_cash_by_portfolio"]:
                self.stdout.write(
                    f"  - {row['portfolio_name']} (#{row['portfolio_id']}): "
                    f"{row['balance']} {row['currency']}"
                )
        else:
            self.stdout.write("  (none)")

        self.stdout.write("")
        self.stdout.write("Bank cash by linked portfolio/currency:")
        if payload["bank_cash_by_portfolio"]:
            for row in payload["bank_cash_by_portfolio"]:
                portfolio_label = row["portfolio_name"] or f"#{row['portfolio_id']}"
                self.stdout.write(
                    f"  - {row['bank_account_name']} ({row['institution_name']}): "
                    f"{row['balance']} {row['currency']} → {portfolio_label}"
                )
        else:
            self.stdout.write("  (none)")

        self.stdout.write("")
        self.stdout.write("Unlinked / unassigned bank accounts:")
        if payload["unlinked_bank_accounts"]:
            for row in payload["unlinked_bank_accounts"]:
                self.stdout.write(
                    f"  - {row['bank_account_name']} ({row['institution_name']}): "
                    f"{row['balance']} {row['currency']} [{row['portfolio_assignment_status']}]"
                )
        else:
            self.stdout.write("  (none)")

        self.stdout.write("")
        self.stdout.write(
            f"Possible duplicate same-date/same-amount broker+bank entries: "
            f"{payload['duplicate_count']}"
        )
        for dup in payload["possible_duplicate_entries"]:
            self.stdout.write(
                f"  - {dup['date']} {dup['amount']} {dup['currency']}: "
                f"broker #{dup['broker_entry_id']} ({dup['broker_portfolio_name']}) "
                f"↔ bank #{dup['bank_movement_id']} ({dup['bank_account_name']})"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Read-only — no data mutated."))
