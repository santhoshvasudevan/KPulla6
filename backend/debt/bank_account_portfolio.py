"""Bank account portfolio ownership and inference (CASH-UNIFY-1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet

from debt.models import BankAccount, CashMovement, FixedDeposit


class PortfolioAssignmentStatus(str, Enum):
    ASSIGNED = "ASSIGNED"
    UNASSIGNED = "UNASSIGNED"
    AMBIGUOUS = "AMBIGUOUS"


class InferenceOutcome(str, Enum):
    INFERRED = "inferred"
    AMBIGUOUS = "ambiguous"
    UNASSIGNED = "unassigned"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"


def bank_account_associated_portfolio_ids(bank_account_id: int) -> set[int]:
    """Portfolios linked via FDs or portfolio-tagged cash movements."""
    portfolio_ids: set[int] = set()
    portfolio_ids.update(
        FixedDeposit.objects.filter(bank_account_id=bank_account_id).values_list(
            "portfolio_id", flat=True
        )
    )
    portfolio_ids.update(
        CashMovement.objects.filter(
            bank_account_id=bank_account_id, portfolio_id__isnull=False
        ).values_list("portfolio_id", flat=True)
    )
    portfolio_ids.discard(None)
    return portfolio_ids


def infer_bank_account_portfolio_id(account: BankAccount) -> int | None:
    """Return the sole associated portfolio id when unambiguous, else None."""
    associated = bank_account_associated_portfolio_ids(account.id)
    if len(associated) == 1:
        return next(iter(associated))
    return None


def bank_account_portfolio_assignment_status(account: BankAccount) -> str:
    if account.portfolio_id:
        return PortfolioAssignmentStatus.ASSIGNED.value
    associated = bank_account_associated_portfolio_ids(account.id)
    if len(associated) > 1:
        return PortfolioAssignmentStatus.AMBIGUOUS.value
    return PortfolioAssignmentStatus.UNASSIGNED.value


@dataclass(frozen=True)
class BankAccountInferenceReport:
    bank_account_id: int
    user_id: int
    account_name: str
    current_portfolio_id: int | None
    inferred_portfolio_id: int | None
    associated_portfolio_ids: frozenset[int]
    outcome: InferenceOutcome
    detail: str


def _bank_accounts_for_inference(
    *,
    user_id: int | None = None,
    bank_account_id: int | None = None,
) -> QuerySet[BankAccount]:
    qs = BankAccount.objects.filter(is_active=True).select_related("portfolio", "user")
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if bank_account_id is not None:
        qs = qs.filter(pk=bank_account_id)
    return qs.order_by("user_id", "name", "id")


def build_bank_account_inference_report(account: BankAccount) -> BankAccountInferenceReport:
    associated = bank_account_associated_portfolio_ids(account.id)
    inferred = infer_bank_account_portfolio_id(account)

    if account.portfolio_id:
        return BankAccountInferenceReport(
            bank_account_id=account.id,
            user_id=account.user_id,
            account_name=account.name,
            current_portfolio_id=account.portfolio_id,
            inferred_portfolio_id=inferred,
            associated_portfolio_ids=frozenset(associated),
            outcome=InferenceOutcome.UNCHANGED,
            detail="Portfolio already assigned on bank account.",
        )

    if len(associated) > 1:
        return BankAccountInferenceReport(
            bank_account_id=account.id,
            user_id=account.user_id,
            account_name=account.name,
            current_portfolio_id=None,
            inferred_portfolio_id=None,
            associated_portfolio_ids=frozenset(associated),
            outcome=InferenceOutcome.AMBIGUOUS,
            detail=(
                f"Multiple portfolios linked ({sorted(associated)}); "
                "manual assignment required."
            ),
        )

    if inferred is None:
        return BankAccountInferenceReport(
            bank_account_id=account.id,
            user_id=account.user_id,
            account_name=account.name,
            current_portfolio_id=None,
            inferred_portfolio_id=None,
            associated_portfolio_ids=frozenset(associated),
            outcome=InferenceOutcome.UNASSIGNED,
            detail="No portfolio signals from fixed deposits or cash movements.",
        )

    return BankAccountInferenceReport(
        bank_account_id=account.id,
        user_id=account.user_id,
        account_name=account.name,
        current_portfolio_id=None,
        inferred_portfolio_id=inferred,
        associated_portfolio_ids=frozenset(associated),
        outcome=InferenceOutcome.INFERRED,
        detail=f"Unambiguous portfolio signal: {inferred}.",
    )


def find_bank_account_inference_reports(
    *,
    user_id: int | None = None,
    bank_account_id: int | None = None,
) -> list[BankAccountInferenceReport]:
    return [
        build_bank_account_inference_report(account)
        for account in _bank_accounts_for_inference(
            user_id=user_id, bank_account_id=bank_account_id
        )
    ]


def apply_bank_account_portfolio_inference(
    account: BankAccount,
    *,
    portfolio_id: int,
) -> BankAccount:
    account.portfolio_id = portfolio_id
    account.save(update_fields=["portfolio", "updated_at"])
    return account


class FixedDepositBankPortfolioError(Exception):
    """FD portfolio must derive from bank account portfolio (CASH-UNIFY-2)."""

    def __init__(
        self,
        detail: str,
        *,
        bank_account_id: int,
        bank_account_portfolio_id: int | None = None,
        bank_account_portfolio_name: str | None = None,
        requested_portfolio_id: int | None = None,
        portfolio_assignment_status: str,
        hint: str,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.bank_account_id = bank_account_id
        self.bank_account_portfolio_id = bank_account_portfolio_id
        self.bank_account_portfolio_name = bank_account_portfolio_name
        self.requested_portfolio_id = requested_portfolio_id
        self.portfolio_assignment_status = portfolio_assignment_status
        self.hint = hint


def resolve_fd_portfolio_from_bank_account(
    bank_account: BankAccount,
    requested_portfolio_id: int | None = None,
):
    """Return the portfolio for a fixed deposit linked to this bank account."""
    from portfolios.models import Portfolio

    status = bank_account_portfolio_assignment_status(bank_account)
    bank_account_id = bank_account.id

    if status == PortfolioAssignmentStatus.AMBIGUOUS.value:
        raise FixedDepositBankPortfolioError(
            detail=(
                "Assign this bank account to a portfolio before creating a Fixed Deposit."
            ),
            bank_account_id=bank_account_id,
            bank_account_portfolio_id=None,
            bank_account_portfolio_name=None,
            requested_portfolio_id=requested_portfolio_id,
            portfolio_assignment_status=status,
            hint=(
                "Multiple portfolios are linked to this bank account. "
                "Assign one portfolio in Settings → Bank Accounts."
            ),
        )

    if not bank_account.portfolio_id:
        raise FixedDepositBankPortfolioError(
            detail=(
                "Assign this bank account to a portfolio before creating a Fixed Deposit."
            ),
            bank_account_id=bank_account_id,
            bank_account_portfolio_id=None,
            bank_account_portfolio_name=None,
            requested_portfolio_id=requested_portfolio_id,
            portfolio_assignment_status=status,
            hint=(
                "Open Settings → Bank Accounts and assign a portfolio to this account."
            ),
        )

    portfolio: Portfolio = bank_account.portfolio
    if (
        requested_portfolio_id is not None
        and requested_portfolio_id != portfolio.id
    ):
        raise FixedDepositBankPortfolioError(
            detail=(
                f"Fixed deposit portfolio must match the bank account portfolio "
                f"({portfolio.name})."
            ),
            bank_account_id=bank_account_id,
            bank_account_portfolio_id=portfolio.id,
            bank_account_portfolio_name=portfolio.name,
            requested_portfolio_id=requested_portfolio_id,
            portfolio_assignment_status=status,
            hint=(
                "Select a bank account linked to the intended portfolio, "
                "or assign the bank account first."
            ),
        )

    return portfolio


def fixed_deposit_portfolio_mismatch_warning(fd: FixedDeposit) -> str | None:
    """Read-only warning when legacy FD portfolio differs from bank account portfolio."""
    bank = fd.bank_account
    if not bank or not bank.portfolio_id:
        return None
    if fd.portfolio_id == bank.portfolio_id:
        return None
    bank_name = bank.portfolio.name if bank.portfolio_id else "unassigned"
    return (
        f"Fixed deposit portfolio ({fd.portfolio.name}) differs from the linked "
        f"bank account portfolio ({bank_name}). Assign or reconcile in Bank Accounts."
    )


def resolve_portfolio_for_bank_account(
    user: AbstractBaseUser,
    portfolio_id: int | None,
) -> None:
    """Validate portfolio_id for bank account create/update; raises BankAccountValidationError."""
    from debt.services import BankAccountValidationError
    from portfolios.services import PortfolioNotFoundError, get_portfolio

    if portfolio_id is None:
        return
    try:
        portfolio = get_portfolio(user, portfolio_id)
    except PortfolioNotFoundError as exc:
        raise BankAccountValidationError(str(exc)) from exc
    if not portfolio.is_active:
        raise BankAccountValidationError(f"Portfolio is inactive: {portfolio_id}")
