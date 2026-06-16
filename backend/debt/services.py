from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction as db_transaction
from django.db.models import QuerySet

from cash.constants import SUPPORTED_CASH_CURRENCIES
from debt.models import BankAccount, FixedDeposit, FixedDepositStatus
from portfolios.models import Portfolio
from portfolios.services import PortfolioNotFoundError, get_portfolio, list_active_portfolios


class BankAccountNotFoundError(Exception):
    pass


class BankAccountValidationError(Exception):
    pass


class FixedDepositNotFoundError(Exception):
    pass


class FixedDepositValidationError(Exception):
    pass


def _validate_currency(currency: str) -> str:
    code = (currency or "").strip().upper()
    if code not in SUPPORTED_CASH_CURRENCIES:
        raise BankAccountValidationError(f"Unsupported currency: {currency}")
    return code


def list_active_bank_accounts(user: AbstractBaseUser) -> list[BankAccount]:
    return list(
        BankAccount.objects.filter(user=user, is_active=True).order_by("name", "id")
    )


def get_bank_account(user: AbstractBaseUser, account_id: int) -> BankAccount:
    account = BankAccount.objects.filter(user=user, pk=account_id).first()
    if not account:
        raise BankAccountNotFoundError(f"Bank account not found: {account_id}")
    return account


def create_bank_account(
    user: AbstractBaseUser,
    *,
    name: str,
    institution_name: str,
    account_number: str,
    currency: str,
    opening_balance: Decimal | None = None,
    current_balance: Decimal | None = None,
    include_in_portfolio_value: bool = False,
    comment: str = "",
) -> BankAccount:
    nm = (name or "").strip()
    if not nm:
        raise BankAccountValidationError("name must not be empty")
    inst = (institution_name or "").strip()
    if not inst:
        raise BankAccountValidationError("institution_name must not be empty")
    acct = (account_number or "").strip()
    if not acct:
        raise BankAccountValidationError("account_number must not be empty")

    account = BankAccount(
        user=user,
        name=nm,
        institution_name=inst,
        account_number=acct,
        currency=_validate_currency(currency),
        opening_balance=opening_balance if opening_balance is not None else Decimal("0"),
        current_balance=current_balance if current_balance is not None else Decimal("0"),
        include_in_portfolio_value=bool(include_in_portfolio_value),
        comment=(comment or "").strip(),
        is_active=True,
    )
    account.save()
    return account


def update_bank_account(
    user: AbstractBaseUser,
    account_id: int,
    *,
    name: str | None = None,
    institution_name: str | None = None,
    account_number: str | None = None,
    currency: str | None = None,
    opening_balance: Decimal | None = None,
    current_balance: Decimal | None = None,
    include_in_portfolio_value: bool | None = None,
    comment: str | None = None,
) -> BankAccount:
    account = get_bank_account(user, account_id)
    if not account.is_active:
        raise BankAccountNotFoundError(f"Bank account not found: {account_id}")

    if name is not None:
        nm = (name or "").strip()
        if not nm:
            raise BankAccountValidationError("name must not be empty")
        account.name = nm
    if institution_name is not None:
        inst = (institution_name or "").strip()
        if not inst:
            raise BankAccountValidationError("institution_name must not be empty")
        account.institution_name = inst
    if account_number is not None:
        acct = (account_number or "").strip()
        if not acct:
            raise BankAccountValidationError("account_number must not be empty")
        account.account_number = acct
    if currency is not None:
        account.currency = _validate_currency(currency)
    if opening_balance is not None:
        account.opening_balance = opening_balance
    if current_balance is not None:
        from debt.bank_ledger_services import bank_account_has_ledger

        if bank_account_has_ledger(account):
            raise BankAccountValidationError(
                "current_balance cannot be edited manually once a cash ledger exists. "
                "Use cash movements or ADJUSTMENT entries instead."
            )
        account.current_balance = current_balance
    if include_in_portfolio_value is not None:
        account.include_in_portfolio_value = bool(include_in_portfolio_value)
    if comment is not None:
        account.comment = (comment or "").strip()

    account.save()
    return account


def deactivate_bank_account(user: AbstractBaseUser, account_id: int) -> BankAccount:
    account = get_bank_account(user, account_id)
    if not account.is_active:
        raise BankAccountNotFoundError(f"Bank account not found: {account_id}")
    account.is_active = False
    account.save()
    return account


def _fixed_deposits_queryset(
    user: AbstractBaseUser,
    *,
    portfolio_ids: list[int] | None = None,
    active_only: bool = True,
) -> QuerySet[FixedDeposit]:
    qs = FixedDeposit.objects.filter(user=user).select_related(
        "portfolio", "bank_account", "renewal_of"
    )
    if active_only:
        qs = qs.filter(is_active=True)
    if portfolio_ids is not None:
        qs = qs.filter(portfolio_id__in=portfolio_ids)
    return qs.order_by("-investment_date", "-id")


def list_fixed_deposits(
    user: AbstractBaseUser,
    *,
    portfolio_ids: list[int] | None = None,
) -> list[FixedDeposit]:
    return list(_fixed_deposits_queryset(user, portfolio_ids=portfolio_ids))


def get_fixed_deposit(user: AbstractBaseUser, fd_id: int) -> FixedDeposit:
    fd = (
        FixedDeposit.objects.filter(user=user, pk=fd_id)
        .select_related("portfolio", "bank_account", "renewal_of")
        .first()
    )
    if not fd:
        raise FixedDepositNotFoundError(f"Fixed deposit not found: {fd_id}")
    return fd


def _resolve_bank_account_for_fd(
    user: AbstractBaseUser, bank_account_id: int
) -> BankAccount:
    account = get_bank_account(user, bank_account_id)
    if not account.is_active:
        raise FixedDepositValidationError("Bank account must be active.")
    return account


def _resolve_portfolio_for_fd(user: AbstractBaseUser, portfolio_id: int) -> Portfolio:
    try:
        portfolio = get_portfolio(user, portfolio_id)
    except PortfolioNotFoundError as exc:
        raise FixedDepositValidationError(str(exc)) from exc
    if not portfolio.is_active:
        raise FixedDepositValidationError(f"Portfolio is inactive: {portfolio_id}")
    return portfolio


def create_fixed_deposit(
    user: AbstractBaseUser,
    *,
    portfolio_id: int,
    bank_account_id: int,
    institution_name: str,
    deposit_account_number: str,
    principal_amount: Decimal,
    currency: str,
    interest_rate_percent: Decimal,
    interest_payout_frequency: str,
    investment_date,
    maturity_date,
    nominee_name: str = "",
    comment: str = "",
    status: str = FixedDepositStatus.ACTIVE,
    renewal_of_id: int | None = None,
    skip_opening_debit: bool = False,
) -> FixedDeposit:
    from debt.bank_ledger_services import (
        InsufficientBankBalanceError,
        bank_account_has_ledger,
        create_fd_opening_cash_movement,
        opening_balance_is_seeded,
        validate_no_overdraft,
    )

    portfolio = _resolve_portfolio_for_fd(user, portfolio_id)
    bank_account = _resolve_bank_account_for_fd(user, bank_account_id)

    renewal_of = None
    if renewal_of_id is not None:
        renewal_of = get_fixed_deposit(user, renewal_of_id)

    fd_currency = _validate_currency(currency)
    if fd_currency != bank_account.currency:
        raise FixedDepositValidationError(
            f"Fixed deposit currency must match linked bank account "
            f"currency ({bank_account.currency})."
        )

    if not skip_opening_debit:
        try:
            validate_no_overdraft(
                bank_account,
                additional_signed=-principal_amount,
                as_of_date=investment_date,
            )
        except InsufficientBankBalanceError as exc:
            if (
                bank_account.opening_balance > 0
                and not opening_balance_is_seeded(bank_account)
                and not bank_account_has_ledger(bank_account)
            ):
                hint = (
                    "Opening balance has not been seeded into the cash ledger yet. "
                    "Use Settings → Bank Accounts → Seed opening balance first."
                )
            else:
                hint = (
                    "For backdated FDs, record or seed bank cash on or before the investment date."
                )
            raise InsufficientBankBalanceError(
                str(exc),
                required=exc.required,
                available=exc.available,
                shortfall=exc.shortfall,
                currency=exc.currency,
                hint=hint,
            ) from exc

    fd = FixedDeposit(
        user=user,
        portfolio=portfolio,
        bank_account=bank_account,
        institution_name=(institution_name or "").strip(),
        deposit_account_number=(deposit_account_number or "").strip(),
        principal_amount=principal_amount,
        currency=fd_currency,
        interest_rate_percent=interest_rate_percent,
        interest_payout_frequency=interest_payout_frequency,
        investment_date=investment_date,
        maturity_date=maturity_date,
        nominee_name=(nominee_name or "").strip(),
        comment=(comment or "").strip(),
        status=status,
        renewal_of=renewal_of,
        is_active=True,
    )
    with db_transaction.atomic():
        try:
            fd.save()
        except DjangoValidationError as exc:
            raise FixedDepositValidationError(
                exc.messages[0] if exc.messages else str(exc)
            ) from exc
        if not skip_opening_debit:
            create_fd_opening_cash_movement(user, fd)
    return fd


def update_fixed_deposit(
    user: AbstractBaseUser,
    fd_id: int,
    **fields,
) -> FixedDeposit:
    from debt.bank_ledger_services import (
        IMMUTABLE_FD_FIELDS_AFTER_OPENING,
        fixed_deposit_has_opening_cash_movement,
    )

    fd = get_fixed_deposit(user, fd_id)
    if not fd.is_active:
        raise FixedDepositNotFoundError(f"Fixed deposit not found: {fd_id}")

    has_opening = fixed_deposit_has_opening_cash_movement(fd.id)
    if has_opening:
        blocked = {
            key
            for key in IMMUTABLE_FD_FIELDS_AFTER_OPENING
            if key in fields and fields[key] is not None
        }
        if "bank_account_id" in blocked and fields["bank_account_id"] == fd.bank_account_id:
            blocked.discard("bank_account_id")
        if "portfolio_id" in blocked and fields["portfolio_id"] == fd.portfolio_id:
            blocked.discard("portfolio_id")
        if "principal_amount" in blocked and fields["principal_amount"] == fd.principal_amount:
            blocked.discard("principal_amount")
        if "currency" in blocked and fields["currency"] == fd.currency:
            blocked.discard("currency")
        if "investment_date" in blocked and fields["investment_date"] == fd.investment_date:
            blocked.discard("investment_date")
        if blocked:
            label = ", ".join(sorted(blocked))
            raise FixedDepositValidationError(
                f"Cannot change {label} after the opening cash movement has been recorded."
            )

    if "portfolio_id" in fields and fields["portfolio_id"] is not None:
        fd.portfolio = _resolve_portfolio_for_fd(user, fields["portfolio_id"])
    if "bank_account_id" in fields and fields["bank_account_id"] is not None:
        fd.bank_account = _resolve_bank_account_for_fd(user, fields["bank_account_id"])
    if "institution_name" in fields and fields["institution_name"] is not None:
        fd.institution_name = (fields["institution_name"] or "").strip()
    if "deposit_account_number" in fields and fields["deposit_account_number"] is not None:
        fd.deposit_account_number = (fields["deposit_account_number"] or "").strip()
    if "principal_amount" in fields and fields["principal_amount"] is not None:
        fd.principal_amount = fields["principal_amount"]
    if "currency" in fields and fields["currency"] is not None:
        fd.currency = _validate_currency(fields["currency"])
    if "interest_rate_percent" in fields and fields["interest_rate_percent"] is not None:
        fd.interest_rate_percent = fields["interest_rate_percent"]
    if "interest_payout_frequency" in fields and fields["interest_payout_frequency"] is not None:
        fd.interest_payout_frequency = fields["interest_payout_frequency"]
    if "investment_date" in fields and fields["investment_date"] is not None:
        fd.investment_date = fields["investment_date"]
    if "maturity_date" in fields and fields["maturity_date"] is not None:
        fd.maturity_date = fields["maturity_date"]
    if "nominee_name" in fields and fields["nominee_name"] is not None:
        fd.nominee_name = (fields["nominee_name"] or "").strip()
    if "comment" in fields and fields["comment"] is not None:
        fd.comment = (fields["comment"] or "").strip()
    if "status" in fields and fields["status"] is not None:
        fd.status = fields["status"]
    if "renewal_of_id" in fields:
        renewal_of_id = fields["renewal_of_id"]
        if renewal_of_id is None:
            fd.renewal_of = None
        else:
            fd.renewal_of = get_fixed_deposit(user, renewal_of_id)

    try:
        fd.save()
    except DjangoValidationError as exc:
        raise FixedDepositValidationError(exc.messages[0] if exc.messages else str(exc)) from exc
    return fd


def deactivate_fixed_deposit(user: AbstractBaseUser, fd_id: int) -> FixedDeposit:
    fd = get_fixed_deposit(user, fd_id)
    if not fd.is_active:
        raise FixedDepositNotFoundError(f"Fixed deposit not found: {fd_id}")
    fd.is_active = False
    fd.save()
    return fd


def list_active_bank_accounts_for_user(user: AbstractBaseUser) -> list[BankAccount]:
    """Alias used by serializers/views."""
    return list_active_bank_accounts(user)


def list_active_portfolios_for_user(user: AbstractBaseUser) -> list[Portfolio]:
    return list_active_portfolios(user)
