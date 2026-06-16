"""Fixed deposit renewal workflow (ORM only, no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction as db_transaction

from debt.bank_ledger_services import create_fd_settlement_cash_movement
from debt.models import (
    FixedDeposit,
    FixedDepositRenewalGroup,
    FixedDepositSettlement,
    FixedDepositSettlementType,
    FixedDepositStatus,
    SETTLEMENT_BLOCKED_FD_STATUSES,
    SETTLEMENT_ELIGIBLE_FD_STATUSES,
)
from debt.services import FixedDepositNotFoundError, create_fixed_deposit, get_fixed_deposit


class RenewalValidationError(Exception):
    pass


@dataclass(frozen=True)
class RenewalResult:
    renewal_group: FixedDepositRenewalGroup
    old_fixed_deposit: FixedDeposit
    new_fixed_deposit: FixedDeposit
    settlement: FixedDepositSettlement
    cash_movement_ids: list[int]


def _validate_fd_for_renewal(fd: FixedDeposit) -> None:
    if not fd.is_active:
        raise FixedDepositNotFoundError(f"Fixed deposit not found: {fd.id}")
    if fd.status in SETTLEMENT_BLOCKED_FD_STATUSES:
        raise RenewalValidationError(
            f"Fixed deposit with status {fd.status} cannot be renewed."
        )
    if fd.status not in SETTLEMENT_ELIGIBLE_FD_STATUSES:
        raise RenewalValidationError(
            f"Fixed deposit with status {fd.status} cannot be renewed."
        )
    if FixedDepositSettlement.objects.filter(fixed_deposit=fd).exists():
        raise RenewalValidationError("This fixed deposit has already been settled.")
    if fd.renewals.exists():
        raise RenewalValidationError("This fixed deposit has already been renewed.")


def _validate_renewal_amounts(
    *,
    old_principal: Decimal,
    new_principal_amount: Decimal,
    direct_reinvest_amount: Decimal,
    cash_payout_amount: Decimal,
    gross_interest: Decimal,
    tax_withheld: Decimal,
) -> tuple[Decimal, Decimal]:
    if new_principal_amount <= 0:
        raise RenewalValidationError("new_principal_amount must be greater than zero.")
    if direct_reinvest_amount <= 0:
        raise RenewalValidationError("direct_reinvest_amount must be greater than zero.")
    if cash_payout_amount < 0:
        raise RenewalValidationError("cash_payout_amount must be zero or positive.")
    if gross_interest < 0:
        raise RenewalValidationError("gross_interest must be zero or positive.")
    if tax_withheld < 0:
        raise RenewalValidationError("tax_withheld must be zero or positive.")
    if tax_withheld > gross_interest:
        raise RenewalValidationError("tax_withheld cannot exceed gross_interest.")
    net_interest = gross_interest - tax_withheld
    total_maturity_value = old_principal + net_interest
    if total_maturity_value <= 0:
        raise RenewalValidationError("Total maturity value must be greater than zero.")
    return net_interest, total_maturity_value


@db_transaction.atomic
def renew_fixed_deposit(
    user: AbstractBaseUser,
    fd_id: int,
    *,
    renewal_date: date,
    new_deposit_account_number: str,
    new_principal_amount: Decimal,
    new_interest_rate_percent: Decimal,
    new_interest_payout_frequency: str,
    new_investment_date: date,
    new_maturity_date: date,
    new_institution_name: str | None = None,
    nominee_name: str | None = None,
    comment: str = "",
    gross_interest: Decimal = Decimal("0"),
    tax_withheld: Decimal = Decimal("0"),
    cash_payout_amount: Decimal = Decimal("0"),
    direct_reinvest_amount: Decimal | None = None,
) -> RenewalResult:
    old_fd = get_fixed_deposit(user, fd_id)
    _validate_fd_for_renewal(old_fd)

    if new_maturity_date <= new_investment_date:
        raise RenewalValidationError("new_maturity_date must be after new_investment_date.")

    resolved_direct_reinvest = (
        new_principal_amount if direct_reinvest_amount is None else direct_reinvest_amount
    )
    if resolved_direct_reinvest != new_principal_amount:
        raise RenewalValidationError(
            "direct_reinvest_amount must match new_principal_amount for direct rollover renewals."
        )

    old_principal = old_fd.principal_amount
    net_interest, total_maturity_value = _validate_renewal_amounts(
        old_principal=old_principal,
        new_principal_amount=new_principal_amount,
        direct_reinvest_amount=resolved_direct_reinvest,
        cash_payout_amount=cash_payout_amount,
        gross_interest=gross_interest,
        tax_withheld=tax_withheld,
    )

    note = (comment or "").strip()
    cash_movement_ids: list[int] = []

    principal_movement = None
    if cash_payout_amount > 0:
        principal_movement = create_fd_settlement_cash_movement(
            user,
            old_fd,
            settlement_type=FixedDepositSettlementType.MATURITY,
            amount=cash_payout_amount,
            movement_date=renewal_date,
            leg="principal",
            description=note or f"FD renewal cash payout: {old_fd.deposit_account_number}",
        )
        cash_movement_ids.append(principal_movement.id)

    interest_movement = None
    if net_interest > 0:
        interest_movement = create_fd_settlement_cash_movement(
            user,
            old_fd,
            settlement_type=FixedDepositSettlementType.MATURITY,
            amount=net_interest,
            movement_date=renewal_date,
            leg="interest",
            description=note or f"FD renewal final interest: {old_fd.deposit_account_number}",
        )
        cash_movement_ids.append(interest_movement.id)

    total_net_proceeds = old_principal + net_interest
    settlement = FixedDepositSettlement(
        user=user,
        fixed_deposit=old_fd,
        bank_account=old_fd.bank_account,
        settlement_type=FixedDepositSettlementType.MATURITY,
        settlement_date=renewal_date,
        principal_returned=old_principal,
        gross_interest=gross_interest,
        tax_withheld=tax_withheld,
        net_interest=net_interest,
        total_net_proceeds=total_net_proceeds,
        currency=old_fd.currency,
        principal_cash_movement=principal_movement,
        interest_cash_movement=interest_movement,
        comment=note,
    )
    try:
        settlement.save()
    except DjangoValidationError as exc:
        raise RenewalValidationError(
            exc.messages[0] if exc.messages else str(exc)
        ) from exc

    old_fd.status = FixedDepositStatus.MATURED_SETTLED
    old_fd.save(update_fields=["status", "updated_at"])

    institution = (
        (new_institution_name or "").strip()
        or old_fd.institution_name
    )
    resolved_nominee = (
        (nominee_name or "").strip()
        if nominee_name is not None
        else old_fd.nominee_name
    )

    new_fd = create_fixed_deposit(
        user,
        portfolio_id=old_fd.portfolio_id,
        bank_account_id=old_fd.bank_account_id,
        institution_name=institution,
        deposit_account_number=(new_deposit_account_number or "").strip(),
        principal_amount=new_principal_amount,
        currency=old_fd.currency,
        interest_rate_percent=new_interest_rate_percent,
        interest_payout_frequency=new_interest_payout_frequency,
        investment_date=new_investment_date,
        maturity_date=new_maturity_date,
        nominee_name=resolved_nominee,
        comment=note,
        status=FixedDepositStatus.ACTIVE,
        renewal_of_id=old_fd.id,
        skip_opening_debit=True,
    )

    renewal_group = FixedDepositRenewalGroup(
        user=user,
        old_fixed_deposit=old_fd,
        new_fixed_deposit=new_fd,
        settlement=settlement,
        renewal_date=renewal_date,
        old_principal=old_principal,
        direct_reinvest_amount=resolved_direct_reinvest,
        cash_payout_amount=cash_payout_amount,
        gross_interest=gross_interest,
        tax_withheld=tax_withheld,
        net_interest=net_interest,
        total_maturity_value=total_maturity_value,
        currency=old_fd.currency,
        comment=note,
    )
    try:
        renewal_group.save()
    except DjangoValidationError as exc:
        raise RenewalValidationError(
            exc.messages[0] if exc.messages else str(exc)
        ) from exc

    return RenewalResult(
        renewal_group=renewal_group,
        old_fixed_deposit=old_fd,
        new_fixed_deposit=new_fd,
        settlement=settlement,
        cash_movement_ids=cash_movement_ids,
    )
