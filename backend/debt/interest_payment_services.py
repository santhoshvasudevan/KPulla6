"""Fixed deposit interest payment services (ORM only, no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction as db_transaction
from django.db.models import QuerySet

from debt.bank_ledger_services import create_fd_interest_cash_movement
from debt.models import (
    COMPOUNDED_FD_INTEREST_WARNING,
    FixedDeposit,
    FixedDepositInterestPayment,
    INTEREST_PAYMENT_BLOCKED_FD_STATUSES,
    InterestPayoutFrequency,
)
from debt.services import FixedDepositNotFoundError, FixedDepositValidationError, get_fixed_deposit


class InterestPaymentNotFoundError(Exception):
    pass


class InterestPaymentValidationError(Exception):
    pass


@dataclass(frozen=True)
class InterestPaymentCreateResult:
    payment: FixedDepositInterestPayment
    warning: str | None = None


def _validate_interest_amounts(
    gross_interest: Decimal,
    tax_withheld: Decimal,
) -> Decimal:
    if gross_interest <= 0:
        raise InterestPaymentValidationError("gross_interest must be greater than zero.")
    if tax_withheld < 0:
        raise InterestPaymentValidationError("tax_withheld must be zero or positive.")
    if tax_withheld > gross_interest:
        raise InterestPaymentValidationError("tax_withheld cannot exceed gross_interest.")
    return gross_interest - tax_withheld


def _validate_fd_for_interest_payment(fd: FixedDeposit) -> str | None:
    if not fd.is_active:
        raise FixedDepositNotFoundError(f"Fixed deposit not found: {fd.id}")
    if fd.status in INTEREST_PAYMENT_BLOCKED_FD_STATUSES:
        raise InterestPaymentValidationError(
            f"Interest payments are not allowed for {fd.status} fixed deposits."
        )
    if fd.interest_payout_frequency == InterestPayoutFrequency.COMPOUNDED:
        return COMPOUNDED_FD_INTEREST_WARNING
    return None


@db_transaction.atomic
def create_fixed_deposit_interest_payment(
    user: AbstractBaseUser,
    fd_id: int,
    *,
    payment_date: date,
    gross_interest: Decimal,
    tax_withheld: Decimal = Decimal("0"),
    comment: str = "",
) -> InterestPaymentCreateResult:
    fd = get_fixed_deposit(user, fd_id)
    warning = _validate_fd_for_interest_payment(fd)
    net_interest = _validate_interest_amounts(gross_interest, tax_withheld)

    description = (comment or "").strip()
    movement = create_fd_interest_cash_movement(
        user,
        fd,
        net_interest=net_interest,
        payment_date=payment_date,
        description=description,
    )

    payment = FixedDepositInterestPayment(
        user=user,
        fixed_deposit=fd,
        bank_account=fd.bank_account,
        payment_date=payment_date,
        gross_interest=gross_interest,
        tax_withheld=tax_withheld,
        net_interest=net_interest,
        currency=fd.currency,
        cash_movement=movement,
        comment=description,
    )
    try:
        payment.save()
    except DjangoValidationError as exc:
        raise InterestPaymentValidationError(
            exc.messages[0] if exc.messages else str(exc)
        ) from exc

    return InterestPaymentCreateResult(payment=payment, warning=warning)


def list_fixed_deposit_interest_payments(
    user: AbstractBaseUser,
    fd_id: int,
) -> list[FixedDepositInterestPayment]:
    fd = get_fixed_deposit(user, fd_id)
    return list(
        FixedDepositInterestPayment.objects.filter(user=user, fixed_deposit=fd)
        .select_related("bank_account", "cash_movement", "fixed_deposit")
        .order_by("-payment_date", "-created_at", "-id")
    )


def get_fixed_deposit_interest_payment(
    user: AbstractBaseUser,
    payment_id: int,
) -> FixedDepositInterestPayment:
    payment = (
        FixedDepositInterestPayment.objects.filter(user=user, pk=payment_id)
        .select_related("bank_account", "cash_movement", "fixed_deposit")
        .first()
    )
    if not payment:
        raise InterestPaymentNotFoundError(
            f"Fixed deposit interest payment not found: {payment_id}"
        )
    return payment


def interest_payments_for_user(user: AbstractBaseUser) -> QuerySet[FixedDepositInterestPayment]:
    return FixedDepositInterestPayment.objects.filter(user=user)
