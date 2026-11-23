"""#46: review and resolve FD maturity payout discrepancies."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from debt import settlement_services
from debt.models import CashMovement, FixedDeposit, FixedDepositPendingPayout
from debt.pending_payout_services import confirm_fixed_deposit_pending_payout
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account
from tests.test_fixed_deposit_pending_payouts_api import (
    _confirm,
    _create_fd,
    _interest_movements,
    _settle_pending,
)


def _resolve(client, pending_id, comment="Bank applied revised TDS; confirmed with branch."):
    return client.post(
        f"/api/v1/fixed-deposit-pending-payouts/{pending_id}/resolve-discrepancy",
        {"comment": comment},
        format="json",
    )


def _open_discrepancy(api_client, user):
    """Suggested net 2000 (2200 - 200), actual net 1850 (2050 - 200)."""
    portfolio = ensure_default_portfolio(user)
    fd = _create_fd(user, portfolio)
    pending_id = _settle_pending(
        api_client, fd, gross_interest="2200", tax_withheld="200"
    ).json()["pending_payout"]["id"]
    confirmed = _confirm(api_client, pending_id, gross_interest="2050", tax_withheld="200")
    assert confirmed.status_code == 201
    return fd, pending_id, confirmed.json()


def _ledger_snapshot(api_client, fd):
    pending = FixedDepositPendingPayout.objects.get(fixed_deposit=fd)
    bank = fd.bank_account
    bank.refresh_from_db()
    movement = pending.cash_movement
    report = api_client.get("/api/v1/reports/fixed-deposit-interest").json()
    detail = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/detail").json()
    return {
        "status": pending.status,
        "suggested": (
            pending.suggested_gross_interest,
            pending.suggested_tax_withheld,
            pending.suggested_net_interest,
        ),
        "actual": (
            pending.payment_date,
            pending.gross_interest,
            pending.tax_withheld,
            pending.net_interest,
        ),
        "discrepancy_amount": pending.discrepancy_amount,
        "movement": (movement.id, movement.amount, movement.movement_date),
        "movement_count": CashMovement.objects.count(),
        "bank_balance": bank.current_balance,
        "fd_status": FixedDeposit.objects.get(id=fd.id).status,
        "report_totals": report["totals"],
        "report_rows": [
            (r["date"], r["gross_interest"], r["tax_withheld"], r["net_interest"])
            for r in report["rows"]
        ],
        "term_totals": detail["term_totals"],
    }


# --- detection --------------------------------------------------------------


@pytest.mark.django_db
def test_net_shortfall_opens_discrepancy_and_posts_actual(api_client, seeded, test_user):
    fd, _pending_id, body = _open_discrepancy(api_client, test_user)

    assert body["suggested_net_interest"] == 2000.0
    assert body["net_interest"] == 1850.0
    assert body["discrepancy_status"] == "OPEN"
    assert body["discrepancy_amount"] == -150.0
    movement = CashMovement.objects.get(id=body["cash_movement_id"])
    assert movement.amount == Decimal("1850")
    assert _interest_movements(fd).count() == 1


@pytest.mark.django_db
def test_matching_net_with_different_gross_split_is_not_flagged(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(
        api_client, fd, gross_interest="2200", tax_withheld="200"
    ).json()["pending_payout"]["id"]

    body = _confirm(api_client, pending_id, gross_interest="2100", tax_withheld="100").json()

    assert body["net_interest"] == 2000.0
    assert body["discrepancy_status"] == "NONE"
    assert body["discrepancy_amount"] is None
    assert _resolve(api_client, pending_id).status_code == 409


@pytest.mark.django_db
def test_missing_estimate_is_not_flagged_and_cannot_be_resolved(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(
        api_client, fd, gross_interest="0", tax_withheld="0"
    ).json()["pending_payout"]["id"]

    body = _confirm(api_client, pending_id, gross_interest="1850", tax_withheld="0").json()

    assert body["discrepancy_status"] == "NONE"
    response = _resolve(api_client, pending_id)
    assert response.status_code == 409
    pending = FixedDepositPendingPayout.objects.get(id=pending_id)
    assert pending.resolution_comment == ""
    assert pending.resolved_at is None


@pytest.mark.django_db
def test_unconfirmed_pending_cannot_be_resolved(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    pending_id = _settle_pending(api_client, fd).json()["pending_payout"]["id"]

    assert _resolve(api_client, pending_id).status_code == 409
    assert FixedDepositPendingPayout.objects.get(id=pending_id).status == "PENDING"


# --- resolution -------------------------------------------------------------


@pytest.mark.django_db
def test_resolve_records_comment_and_preserves_ledger(api_client, seeded, test_user):
    fd, pending_id, _ = _open_discrepancy(api_client, test_user)
    before = _ledger_snapshot(api_client, fd)

    response = _resolve(api_client, pending_id, comment="  Bank deducted extra TDS.  ")

    assert response.status_code == 200
    body = response.json()
    assert body["discrepancy_status"] == "RESOLVED"
    assert body["discrepancy_amount"] == -150.0
    assert body["resolution_comment"] == "Bank deducted extra TDS."
    assert body["resolved_at"] is not None
    assert body["net_interest"] == 1850.0
    assert body["suggested_net_interest"] == 2000.0
    assert _ledger_snapshot(api_client, fd) == before


@pytest.mark.django_db
def test_resolution_persists_on_reload_and_originating_term(api_client, seeded, test_user):
    fd, pending_id, _ = _open_discrepancy(api_client, test_user)
    open_items = api_client.get(
        "/api/v1/fixed-deposit-pending-payouts?status=all&discrepancy_status=open"
    ).json()
    assert [item["id"] for item in open_items] == [pending_id]

    assert _resolve(api_client, pending_id, comment="Accepted bank figure.").status_code == 200

    detail = api_client.get(f"/api/v1/fixed-deposit-pending-payouts/{pending_id}").json()
    assert detail["discrepancy_status"] == "RESOLVED"
    assert detail["resolution_comment"] == "Accepted bank figure."

    history = api_client.get("/api/v1/fixed-deposits?lifecycle_view=history").json()
    term = next(item for item in history if item["id"] == fd.id)
    assert term["pending_payout"]["discrepancy_status"] == "RESOLVED"
    assert term["pending_payout"]["discrepancy_amount"] == -150.0
    assert term["pending_payout"]["resolution_comment"] == "Accepted bank figure."
    assert term["pending_payout"]["resolved_at"] == detail["resolved_at"]

    fd_detail = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/detail").json()
    assert fd_detail["pending_payout"]["discrepancy_status"] == "RESOLVED"
    assert fd_detail["pending_payout"]["resolution_comment"] == "Accepted bank figure."

    assert api_client.get(
        "/api/v1/fixed-deposit-pending-payouts?status=all&discrepancy_status=open"
    ).json() == []
    resolved_items = api_client.get(
        "/api/v1/fixed-deposit-pending-payouts?status=confirmed&discrepancy_status=resolved"
    ).json()
    assert [item["id"] for item in resolved_items] == [pending_id]


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [{}, {"comment": ""}, {"comment": "   "}])
def test_resolve_requires_comment(api_client, seeded, test_user, payload):
    _fd, pending_id, _ = _open_discrepancy(api_client, test_user)

    response = api_client.post(
        f"/api/v1/fixed-deposit-pending-payouts/{pending_id}/resolve-discrepancy",
        payload,
        format="json",
    )

    assert response.status_code == 400
    pending = FixedDepositPendingPayout.objects.get(id=pending_id)
    assert pending.discrepancy_status == "OPEN"
    assert pending.resolved_at is None


@pytest.mark.django_db
def test_second_resolve_conflicts_and_keeps_first_comment(api_client, seeded, test_user):
    _fd, pending_id, _ = _open_discrepancy(api_client, test_user)
    first = _resolve(api_client, pending_id, comment="First review.")
    assert first.status_code == 200

    second = _resolve(api_client, pending_id, comment="Second review.")

    assert second.status_code == 409
    pending = FixedDepositPendingPayout.objects.get(id=pending_id)
    assert pending.resolution_comment == "First review."
    assert pending.resolved_at.isoformat() == first.json()["resolved_at"]


@pytest.mark.django_db
def test_list_rejects_unknown_discrepancy_filter(api_client, seeded, test_user):
    response = api_client.get(
        "/api/v1/fixed-deposit-pending-payouts?status=all&discrepancy_status=bogus"
    )
    assert response.status_code == 400


# --- access control ---------------------------------------------------------


@pytest.mark.django_db
def test_resolve_requires_authentication(api_client, anon_client, seeded, test_user):
    _fd, pending_id, _ = _open_discrepancy(api_client, test_user)

    response = _resolve(anon_client, pending_id)

    assert response.status_code in (401, 403)
    assert FixedDepositPendingPayout.objects.get(id=pending_id).discrepancy_status == "OPEN"


@pytest.mark.django_db
def test_other_users_discrepancy_returns_404(api_client, seeded, test_user, other_user):
    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="INR", is_active=True
    )
    other_fd = _create_fd(
        other_user,
        other_portfolio,
        bank=create_test_bank_account(other_user, portfolio=other_portfolio),
    )
    result = settlement_services.create_fixed_deposit_settlement(
        other_user,
        other_fd.id,
        settlement_type="MATURITY",
        settlement_date=date(2026, 1, 1),
        gross_interest=Decimal("2000"),
        final_interest_pending=True,
    )
    confirm_fixed_deposit_pending_payout(
        other_user,
        result.pending_payout.id,
        payment_date=date(2026, 1, 5),
        gross_interest=Decimal("1850"),
    )

    response = _resolve(api_client, result.pending_payout.id)

    assert response.status_code == 404
    pending = FixedDepositPendingPayout.objects.get(id=result.pending_payout.id)
    assert pending.discrepancy_status == "OPEN"
    assert pending.resolution_comment == ""
