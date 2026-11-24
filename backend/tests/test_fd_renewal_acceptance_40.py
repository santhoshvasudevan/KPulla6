"""#40 integrated acceptance: renewal with a delayed, short final interest payout."""

from __future__ import annotations

from decimal import Decimal

import pytest

from debt.models import CashMovement, CashMovementType
from portfolios.seed import ensure_default_portfolio
from tests.test_fixed_deposit_pending_payouts_api import _confirm, _create_fd, _renew_payload

AUDIT_URL = "/api/v1/reports/fixed-deposit-renewal-audit"


def _value_history(api_client):
    payload = api_client.get(
        "/api/v1/portfolio/performance?metric=value&range=ALL&display_currency=INR"
    ).json()
    points = payload["points"] if isinstance(payload, dict) else payload
    return {p["date"]: p["value"] for p in points}


def _final_interest_credits(fd):
    return CashMovement.objects.filter(
        linked_fixed_deposit=fd,
        movement_type__in=[
            CashMovementType.FD_MATURITY_INTEREST,
            CashMovementType.FD_CLOSURE_INTEREST,
        ],
    )


def _audit_for(api_client, fd):
    results = api_client.get(AUDIT_URL).json()["results"]
    return next(r for r in results if r["old_term"]["id"] == fd.id)


@pytest.mark.django_db
def test_renewal_with_delayed_short_payout_end_to_end(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    fd = _create_fd(test_user, portfolio)
    bank = fd.bank_account

    # Renew with final interest pending: estimate 2200 gross / 200 TDS = 2000 net.
    renew = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        _renew_payload(
            new_principal_amount="90000",
            cash_payout_amount="10000",
            gross_interest="2200",
            tax_withheld="200",
            final_interest_pending=True,
            pending_expected_date="2026-01-10",
        ),
        format="json",
    )
    assert renew.status_code == 201
    body = renew.json()
    successor_id = body["new_fixed_deposit"]["id"]
    pending_id = body["pending_payout"]["id"]
    assert body["net_interest"] == 0.0
    assert body["pending_payout"]["suggested_net_interest"] == 2000.0
    assert not _final_interest_credits(fd).exists()

    # Current shows only the successor; History holds the renewed predecessor.
    current = api_client.get("/api/v1/fixed-deposits?lifecycle_view=current").json()
    history = api_client.get("/api/v1/fixed-deposits?lifecycle_view=history").json()
    assert [item["id"] for item in current] == [successor_id]
    assert [item["id"] for item in history] == [fd.id]
    assert history[0]["is_renewed"] is True
    assert history[0]["next_term_id"] == successor_id
    assert history[0]["pending_payout"]["status"] == "PENDING"

    assert _audit_for(api_client, fd)["status"] == "INCOMPLETE"
    report_before = api_client.get("/api/v1/reports/fixed-deposit-interest").json()
    assert report_before["rows"] == []

    # Bank pays late and short: 2050 gross / 200 TDS = 1850 net.
    bank.refresh_from_db()
    balance_before_payout = bank.current_balance
    confirmed = _confirm(
        api_client, pending_id, payment_date="2026-01-15", gross_interest="2050", tax_withheld="200"
    )
    assert confirmed.status_code == 201
    payout = confirmed.json()
    assert payout["net_interest"] == 1850.0
    assert payout["discrepancy_status"] == "OPEN"
    assert payout["discrepancy_amount"] == -150.0

    credits = list(_final_interest_credits(fd))
    assert len(credits) == 1
    assert credits[0].amount == Decimal("1850")
    assert str(credits[0].movement_date) == "2026-01-15"
    bank.refresh_from_db()
    assert bank.current_balance == balance_before_payout + Decimal("1850")

    report = api_client.get("/api/v1/reports/fixed-deposit-interest").json()
    assert len(report["rows"]) == 1
    row = report["rows"][0]
    assert row["fixed_deposit_id"] == fd.id
    assert row["source_type"] == "PENDING_PAYOUT"
    assert row["net_interest"] == 1850.0
    assert report["totals"]["net_interest"] == 1850.0
    predecessor_detail = api_client.get(f"/api/v1/fixed-deposits/{fd.id}/detail").json()
    successor_detail = api_client.get(f"/api/v1/fixed-deposits/{successor_id}/detail").json()
    assert predecessor_detail["term_totals"]["actual_net_interest"] == 1850.0
    assert successor_detail["term_totals"]["actual_net_interest"] == 0.0

    audit = _audit_for(api_client, fd)
    assert audit["status"] == "INCOMPLETE"
    assert [f["code"] for f in audit["findings"]] == ["PAYOUT_DISCREPANCY_OPEN"]

    # Resolve with a comment: review metadata only.
    resolved = api_client.post(
        f"/api/v1/fixed-deposit-pending-payouts/{pending_id}/resolve-discrepancy",
        {"comment": "Bank applied higher TDS; matches statement."},
        format="json",
    )
    assert resolved.status_code == 200
    assert resolved.json()["discrepancy_status"] == "RESOLVED"
    assert list(_final_interest_credits(fd)) == credits
    bank.refresh_from_db()
    assert bank.current_balance == balance_before_payout + Decimal("1850")
    report_after = api_client.get("/api/v1/reports/fixed-deposit-interest").json()
    assert report_after["totals"] == report["totals"]
    amounts = ("fixed_deposit_id", "date", "gross_interest", "tax_withheld", "net_interest")
    assert [{k: r[k] for k in amounts} for r in report_after["rows"]] == [
        {k: row[k] for k in amounts}
    ]
    assert report_after["rows"][0]["discrepancy_status"] == "RESOLVED"

    audit = _audit_for(api_client, fd)
    assert audit["status"] == "CONSISTENT"
    assert audit["totals"]["confirmed_later_payout_net"] == 1850.0
    assert audit["totals"]["ledger_payout_total"] == 10000.0

    # Value history: predecessor through the day before settlement, successor from it.
    values = _value_history(api_client)
    assert values["2024-01-01"] == pytest.approx(100000.0, rel=1e-6)
    assert values["2025-12-31"] == pytest.approx(100000.0, rel=1e-6)
    assert values["2026-01-01"] == pytest.approx(90000.0, rel=1e-6)
    assert values["2026-01-15"] == pytest.approx(90000.0, rel=1e-6)
