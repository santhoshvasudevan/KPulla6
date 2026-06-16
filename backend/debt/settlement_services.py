"""Fixed deposit maturity/closure settlement services (ORM only, no HTTP)."""

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
    FixedDepositSettlement,
    FixedDepositSettlementType,
    FixedDepositStatus,
    SETTLEMENT_BLOCKED_FD_STATUSES,
    SETTLEMENT_ELIGIBLE_FD_STATUSES,
)
from debt.services import FixedDepositNotFoundError, get_fixed_deposit


class SettlementNotFoundError(Exception):
    pass


class SettlementValidationError(Exception):
    pass


@dataclass(frozen=True)
class SettlementCreateResult:
    settlement: FixedDepositSettlement
    fixed_deposit: FixedDeposit


def _validate_settlement_amounts(
    *,
    principal_returned: Decimal,
    gross_interest: Decimal,
    tax_withheld: Decimal,
) -> tuple[Decimal, Decimal]:
    if principal_returned < 0:
        raise SettlementValidationError("principal_returned must be zero or positive.")
    if gross_interest < 0:
        raise SettlementValidationError("gross_interest must be zero or positive.")
    if tax_withheld < 0:
        raise SettlementValidationError("tax_withheld must be zero or positive.")
    if tax_withheld > gross_interest:
        raise SettlementValidationError("tax_withheld cannot exceed gross_interest.")
    net_interest = gross_interest - tax_withheld
    total_net_proceeds = principal_returned + net_interest
    if total_net_proceeds <= 0:
        raise SettlementValidationError(
            "At least one of principal_returned or net_interest must be greater than zero."
        )
    return net_interest, total_net_proceeds


def _validate_fd_for_settlement(fd: FixedDeposit) -> None:
    if not fd.is_active:
        raise FixedDepositNotFoundError(f"Fixed deposit not found: {fd.id}")
    if fd.status in SETTLEMENT_BLOCKED_FD_STATUSES:
        raise SettlementValidationError(
            f"Fixed deposit with status {fd.status} cannot be settled."
        )
    if fd.status not in SETTLEMENT_ELIGIBLE_FD_STATUSES:
        raise SettlementValidationError(
            f"Fixed deposit with status {fd.status} cannot be settled."
        )
    if FixedDepositSettlement.objects.filter(fixed_deposit=fd).exists():
        raise SettlementValidationError("This fixed deposit has already been settled.")


def mark_fixed_deposit_matured(user: AbstractBaseUser, fd_id: int) -> FixedDeposit:
    fd = get_fixed_deposit(user, fd_id)
    if not fd.is_active:
        raise FixedDepositNotFoundError(f"Fixed deposit not found: {fd_id}")
    if fd.status in SETTLEMENT_BLOCKED_FD_STATUSES:
        raise SettlementValidationError(
            f"Cannot mark {fd.status} fixed deposit as matured."
        )
    if fd.status == FixedDepositStatus.MATURED:
        return fd
    if fd.status != FixedDepositStatus.ACTIVE:
        raise SettlementValidationError(
            f"Only ACTIVE fixed deposits can be marked matured (current status: {fd.status})."
        )
    fd.status = FixedDepositStatus.MATURED
    fd.save(update_fields=["status", "updated_at"])
    return fd


@db_transaction.atomic
def create_fixed_deposit_settlement(
    user: AbstractBaseUser,
    fd_id: int,
    *,
    settlement_type: str,
    settlement_date: date,
    principal_returned: Decimal | None = None,
    gross_interest: Decimal = Decimal("0"),
    tax_withheld: Decimal = Decimal("0"),
    comment: str = "",
) -> SettlementCreateResult:
    fd = get_fixed_deposit(user, fd_id)
    _validate_fd_for_settlement(fd)

    if settlement_type not in FixedDepositSettlementType.values:
        raise SettlementValidationError("settlement_type must be MATURITY or CLOSURE.")

    resolved_principal = (
        fd.principal_amount if principal_returned is None else principal_returned
    )
    net_interest, total_net_proceeds = _validate_settlement_amounts(
        principal_returned=resolved_principal,
        gross_interest=gross_interest,
        tax_withheld=tax_withheld,
    )

    note = (comment or "").strip()
    principal_movement = None
    if resolved_principal > 0:
        principal_movement = create_fd_settlement_cash_movement(
            user,
            fd,
            settlement_type=settlement_type,
            amount=resolved_principal,
            movement_date=settlement_date,
            leg="principal",
            description=note,
        )

    interest_movement = None
    if net_interest > 0:
        interest_movement = create_fd_settlement_cash_movement(
            user,
            fd,
            settlement_type=settlement_type,
            amount=net_interest,
            movement_date=settlement_date,
            leg="interest",
            description=note,
        )

    settlement = FixedDepositSettlement(
        user=user,
        fixed_deposit=fd,
        bank_account=fd.bank_account,
        settlement_type=settlement_type,
        settlement_date=settlement_date,
        principal_returned=resolved_principal,
        gross_interest=gross_interest,
        tax_withheld=tax_withheld,
        net_interest=net_interest,
        total_net_proceeds=total_net_proceeds,
        currency=fd.currency,
        principal_cash_movement=principal_movement,
        interest_cash_movement=interest_movement,
        comment=note,
    )
    try:
        settlement.save()
    except DjangoValidationError as exc:
        raise SettlementValidationError(
            exc.messages[0] if exc.messages else str(exc)
        ) from exc

    if settlement_type == FixedDepositSettlementType.MATURITY:
        fd.status = FixedDepositStatus.MATURED_SETTLED
    else:
        fd.status = FixedDepositStatus.CLOSED
    fd.save(update_fields=["status", "updated_at"])

    return SettlementCreateResult(settlement=settlement, fixed_deposit=fd)


def list_fixed_deposit_settlements(
    user: AbstractBaseUser,
    fd_id: int,
) -> list[FixedDepositSettlement]:
    fd = get_fixed_deposit(user, fd_id)
    settlement = (
        FixedDepositSettlement.objects.filter(user=user, fixed_deposit=fd)
        .select_related(
            "bank_account",
            "principal_cash_movement",
            "interest_cash_movement",
            "fixed_deposit",
        )
        .first()
    )
    return [settlement] if settlement else []


def get_fixed_deposit_settlement(
    user: AbstractBaseUser,
    settlement_id: int,
) -> FixedDepositSettlement:
    settlement = (
        FixedDepositSettlement.objects.filter(user=user, pk=settlement_id)
        .select_related(
            "bank_account",
            "principal_cash_movement",
            "interest_cash_movement",
            "fixed_deposit",
        )
        .first()
    )
    if not settlement:
        raise SettlementNotFoundError(f"Fixed deposit settlement not found: {settlement_id}")
    return settlement
