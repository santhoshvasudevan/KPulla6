"""Read-only bank account balance timeline for FD funding diagnostics."""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from debt.bank_ledger_services import (
    compute_bank_account_balance,
    compute_bank_funding_balance,
)
from debt.models import BankAccount, CashMovement


class Command(BaseCommand):
    help = (
        "Print bank cash movements and ledger vs funding balances for a date range "
        "(read-only diagnostic)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--bank-account-id", type=int, required=True)
        parser.add_argument("--from", dest="from_date", required=True, help="YYYY-MM-DD")
        parser.add_argument("--to", dest="to_date", required=True, help="YYYY-MM-DD")

    def handle(self, *args, **options):
        account_id = options["bank_account_id"]
        from_date = date.fromisoformat(options["from_date"])
        to_date = date.fromisoformat(options["to_date"])
        if to_date < from_date:
            raise CommandError("--to must be on or after --from")

        account = BankAccount.objects.filter(pk=account_id).first()
        if account is None:
            raise CommandError(f"Bank account not found: {account_id}")

        self.stdout.write(
            f"Bank account #{account.id} {account.name} ({account.institution_name}) "
            f"{account.currency} portfolio_id={account.portfolio_id}"
        )
        self.stdout.write(f"Current ledger balance: {account.current_balance}")
        self.stdout.write(
            f"Computed ledger balance: {compute_bank_account_balance(account)}"
        )
        self.stdout.write(
            f"Funding balance as of {to_date}: "
            f"{compute_bank_funding_balance(account, as_of_date=to_date)}"
        )

        movements = (
            CashMovement.objects.filter(
                bank_account_id=account_id,
                movement_date__gte=from_date,
                movement_date__lte=to_date,
            )
            .order_by("movement_date", "id")
            .select_related("portfolio", "linked_fixed_deposit", "reverses")
        )
        self.stdout.write(f"\nMovements {from_date} .. {to_date} ({movements.count()}):")
        for movement in movements:
            self.stdout.write(
                f"  id={movement.id} date={movement.movement_date} "
                f"type={movement.movement_type} dir={movement.direction} "
                f"amt={movement.amount} portfolio_id={movement.portfolio_id} "
                f"source={movement.source} fd_id={movement.linked_fixed_deposit_id} "
                f"reverses={movement.reverses_id} is_reversal={movement.is_reversal} "
                f"desc={movement.description!r}"
            )

        for label, as_of in [
            (from_date.isoformat(), from_date),
            (to_date.isoformat(), to_date),
        ]:
            ledger = compute_bank_account_balance(account, as_of_date=as_of)
            funding = compute_bank_funding_balance(account, as_of_date=as_of)
            self.stdout.write(
                f"\nAs of {label}: ledger={ledger} funding={funding}"
            )
