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
