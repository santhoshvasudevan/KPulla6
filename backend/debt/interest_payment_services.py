"""Fixed deposit interest payment services (ORM only, no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction as db_transaction
from django.db.models import QuerySet

from debt.bank_ledger_services import (
    create_fd_interest_cash_movement,
    movement_has_been_reversed,
    refresh_bank_account_balance,
)
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


@db_transaction.atomic
def update_fixed_deposit_interest_payment(
    user: AbstractBaseUser,
    payment_id: int,
    *,
    payment_date: date | None = None,
    gross_interest: Decimal | None = None,
    tax_withheld: Decimal | None = None,
    comment: str | None = None,
) -> FixedDepositInterestPayment:
    payment = get_fixed_deposit_interest_payment(user, payment_id)
    if payment.is_reversed:
        raise InterestPaymentValidationError(
            "Reversed interest payments cannot be edited. Record a new payment instead."
        )
    movement = payment.cash_movement
    if movement is None or movement_has_been_reversed(movement):
        raise InterestPaymentValidationError(
            "Linked bank cash movement is missing or reversed; payment cannot be edited."
        )

    new_date = payment_date if payment_date is not None else payment.payment_date
    new_gross = gross_interest if gross_interest is not None else payment.gross_interest
    new_tax = tax_withheld if tax_withheld is not None else payment.tax_withheld
    net_interest = _validate_interest_amounts(new_gross, new_tax)

    if comment is not None:
        description = comment.strip()
        payment.comment = description
    else:
        description = payment.comment

    if not description:
        description = (
            f"Fixed deposit interest: {payment.fixed_deposit.institution_name}/"
            f"{payment.fixed_deposit.deposit_account_number}"
        )

    payment.payment_date = new_date
    payment.gross_interest = new_gross
    payment.tax_withheld = new_tax
    payment.net_interest = net_interest
    payment.save(
        update_fields=[
            "payment_date",
            "gross_interest",
            "tax_withheld",
            "net_interest",
            "comment",
            "updated_at",
        ]
    )

    movement.amount = net_interest
    movement.movement_date = new_date
    movement.description = description
    movement.save(update_fields=["amount", "movement_date", "description", "updated_at"])
    refresh_bank_account_balance(payment.bank_account)
    return payment


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
