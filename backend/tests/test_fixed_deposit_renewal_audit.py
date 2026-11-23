"""#44: read-only audit of recorded FD renewals (service, command, API)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from debt.models import (
    BankAccount,
    CashMovement,
    FixedDeposit,
    FixedDepositInterestPayment,
    FixedDepositPendingPayout,
    FixedDepositRenewalGroup,
    FixedDepositSettlement,
)
from debt.renewal_audit_services import audit_fixed_deposit_renewals
from debt.renewal_services import renew_fixed_deposit
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account
from tests.test_fixed_deposit_pending_payouts_api import _confirm, _create_fd, _renew_payload

AUDIT_URL = "/api/v1/reports/fixed-deposit-renewal-audit"


def _renew(api_client, fd, **overrides):
    response = api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew", _renew_payload(**overrides), format="json"
    )
    assert response.status_code == 201, response.json()
    return response.json()


def _quarterly_fd(user, portfolio, number):
    return _create_fd(
        user,
        portfolio,
        deposit_account_number=number,
        interest_payout_frequency="QUARTERLY",
    )


def _build_scenarios(api_client, user):
    """Synthetic renewals; corrupt rows simulate legacy (pre-#43) or damaged records."""
    portfolio = ensure_default_portfolio(user)
    ids = {}

    fd = _quarterly_fd(user, portfolio, "FULL")
    _renew(api_client, fd, new_principal_amount="104500", gross_interest="5000", tax_withheld="500")
    ids["full_rollover"] = fd.id

    fd = _quarterly_fd(user, portfolio, "PARTIAL")
    _renew(
        api_client,
        fd,
        new_principal_amount="94500",
        cash_payout_amount="10000",
        gross_interest="5000",
        tax_withheld="500",
    )
    ids["partial_rollover"] = fd.id

    fd = _quarterly_fd(user, portfolio, "CONFIRMED")
    pending_id = _renew(
        api_client, fd, gross_interest="5000", tax_withheld="500", final_interest_pending=True
    )["pending_payout"]["id"]
    assert _confirm(api_client, pending_id, gross_interest="5000", tax_withheld="500").status_code == 201
    ids["confirmed_payout"] = fd.id

    # Legacy: full rollover of principal + interest, but the interest was also credited.
    fd = _quarterly_fd(user, portfolio, "LEGACY-CREDIT")
    body = _renew(
        api_client,
        fd,
        cash_payout_amount="4500",
        gross_interest="5000",
        tax_withheld="500",
    )
    FixedDepositRenewalGroup.objects.filter(id=body["renewal_id"]).update(
        direct_reinvest_amount=Decimal("104500"), cash_payout_amount=Decimal("0")
    )
    FixedDeposit.objects.filter(id=body["new_fixed_deposit"]["id"]).update(
        principal_amount=Decimal("104500")
    )
    ids["legacy_interest_credit"] = fd.id

    # Legacy: final interest recorded but neither reinvested nor paid out.
    fd = _quarterly_fd(user, portfolio, "LEGACY-GAP")
    body = _renew(api_client, fd)
    FixedDepositRenewalGroup.objects.filter(id=body["renewal_id"]).update(
        gross_interest=Decimal("5000"),
        tax_withheld=Decimal("500"),
        net_interest=Decimal("4500"),
        total_maturity_value=Decimal("104500"),
    )
    FixedDepositSettlement.objects.filter(fixed_deposit_id=fd.id).update(
        gross_interest=Decimal("5000"),
        tax_withheld=Decimal("500"),
        net_interest=Decimal("4500"),
        total_net_proceeds=Decimal("104500"),
    )
    ids["allocation_gap"] = fd.id

    fd = _quarterly_fd(user, portfolio, "PENDING")
    _renew(api_client, fd, gross_interest="5000", tax_withheld="500", final_interest_pending=True)
    ids["pending_interest"] = fd.id

    # Payout recorded with no bank credit at all.
    fd = _quarterly_fd(user, portfolio, "NO-CREDIT")
    body = _renew(api_client, fd)
    FixedDepositRenewalGroup.objects.filter(id=body["renewal_id"]).update(
        direct_reinvest_amount=Decimal("90000"), cash_payout_amount=Decimal("10000")
    )
    FixedDeposit.objects.filter(id=body["new_fixed_deposit"]["id"]).update(
        principal_amount=Decimal("90000")
    )
    ids["missing_credit"] = fd.id

    # Bank credit exists on the term but is detached from the settlement.
    fd = _quarterly_fd(user, portfolio, "DETACHED")
    _renew(api_client, fd, new_principal_amount="90000", cash_payout_amount="10000")
    FixedDepositSettlement.objects.filter(fixed_deposit_id=fd.id).update(
        principal_cash_movement=None
    )
    ids["detached_credit"] = fd.id
    return ids


EXPECTED = {
    "full_rollover": ("CONSISTENT", []),
    "partial_rollover": ("CONSISTENT", []),
    "confirmed_payout": ("CONSISTENT", []),
    "legacy_interest_credit": ("INCONSISTENT", ["LEDGER_PAYOUT_MISMATCH"]),
    "allocation_gap": ("INCONSISTENT", ["ALLOCATION_MISMATCH"]),
    "pending_interest": ("INCOMPLETE", ["FINAL_INTEREST_PENDING"]),
    "missing_credit": ("INCOMPLETE", ["MISSING_PAYOUT_MOVEMENTS"]),
    "detached_credit": (
        "INCOMPLETE",
        ["MISSING_PAYOUT_MOVEMENTS", "UNLINKED_MATURITY_MOVEMENT"],
    ),
}


def _rows(model):
    return list(model.objects.order_by("id").values())


def _snapshot(api_client):
    return {
        "fixed_deposits": _rows(FixedDeposit),
        "settlements": _rows(FixedDepositSettlement),
        "renewals": _rows(FixedDepositRenewalGroup),
        "pending_payouts": _rows(FixedDepositPendingPayout),
        "interest_payments": _rows(FixedDepositInterestPayment),
        "cash_movements": _rows(CashMovement),
        "bank_accounts": _rows(BankAccount),
        "bank_balances": [
            api_client.get(f"/api/v1/bank-accounts/{bank.id}/balance").json()
            for bank in BankAccount.objects.order_by("id")
        ],
        "interest_report": api_client.get("/api/v1/reports/fixed-deposit-interest").json(),
        "fd_list": api_client.get("/api/v1/fixed-deposits").json(),
    }


def _by_old_fd(results):
    return {r["old_term"]["id"]: r for r in results}


def _assert_expected(results, ids):
    by_fd = _by_old_fd(results)
    for name, (status, codes) in EXPECTED.items():
        result = by_fd[ids[name]]
        assert result["status"] == status, (name, result["findings"])
        assert [f["code"] for f in result["findings"]] == codes, name
        assert all(f["message"] for f in result["findings"])


def _assert_select_only(queries):
    writes = [
        q["sql"]
        for q in queries
        if q["sql"].lstrip().split(" ", 1)[0].upper() in {"INSERT", "UPDATE", "DELETE"}
    ]
    assert writes == []


# --- service ----------------------------------------------------------------


@pytest.mark.django_db
def test_service_classifies_scenarios_with_select_only_queries(api_client, seeded, test_user):
    ids = _build_scenarios(api_client, test_user)
    before = _snapshot(api_client)

    with CaptureQueriesContext(connection) as ctx:
        report = audit_fixed_deposit_renewals(user_id=test_user.id)

    _assert_select_only(ctx.captured_queries)
    assert _snapshot(api_client) == before
    by_fd = {r.old_term.id: r for r in report.results}
    for name, (status, codes) in EXPECTED.items():
        assert by_fd[ids[name]].status == status, name
        assert [f.code for f in by_fd[ids[name]].findings] == codes, name
    assert report.summary.status_counts == {
        "CONSISTENT": 3,
        "INCONSISTENT": 2,
        "INCOMPLETE": 3,
    }


@pytest.mark.django_db
def test_totals_and_term_references_are_reviewable(api_client, seeded, test_user):
    ids = _build_scenarios(api_client, test_user)

    report = audit_fixed_deposit_renewals(user_id=test_user.id)
    by_fd = {r.old_term.id: r for r in report.results}

    partial = by_fd[ids["partial_rollover"]]
    assert partial.old_term.deposit_account_number == "PARTIAL"
    assert partial.new_term.deposit_account_number == "FD-002"
    assert partial.settlement_id is not None
    assert len(partial.settlement_movement_ids) == 2
    assert partial.totals.total_available == Decimal("104500")
    assert partial.totals.ledger_interest_total == Decimal("4500")
    assert partial.totals.ledger_principal_total == Decimal("5500")

    pending = by_fd[ids["pending_interest"]]
    assert pending.totals.net_interest == Decimal("0")
    assert pending.totals.pending_estimate_net == Decimal("4500")
    assert pending.pending_payout_id is not None

    confirmed = by_fd[ids["confirmed_payout"]]
    assert confirmed.totals.confirmed_later_payout_net == Decimal("4500")
    assert confirmed.unlinked_movement_ids == ()

    legacy = by_fd[ids["legacy_interest_credit"]]
    assert legacy.totals.ledger_payout_total == Decimal("4500")
    assert legacy.totals.cash_payout_recorded == Decimal("0")

    (inr,) = report.summary.totals_by_currency
    assert inr.renewal_count == 8
    assert inr.pending_estimate_net == Decimal("4500")
    assert inr.confirmed_later_payout_net == Decimal("4500")


# --- command ----------------------------------------------------------------


@pytest.mark.django_db
def test_command_json_reports_findings_and_writes_nothing(api_client, seeded, test_user):
    ids = _build_scenarios(api_client, test_user)
    before = _snapshot(api_client)
    out = StringIO()

    with CaptureQueriesContext(connection) as ctx:
        call_command("audit_fd_renewals", "--json", stdout=out)

    _assert_select_only(ctx.captured_queries)
    assert _snapshot(api_client) == before
    payload = json.loads(out.getvalue())
    assert payload["read_only"] is True
    assert payload["summary"]["renewal_count"] == 8
    _assert_expected(payload["results"], ids)


@pytest.mark.django_db
def test_command_text_output_and_user_filter(api_client, seeded, test_user, other_user):
    _build_scenarios(api_client, test_user)
    before = _snapshot(api_client)

    out = StringIO()
    call_command("audit_fd_renewals", "--user-id", str(test_user.id), stdout=out)
    text = out.getvalue()
    assert "3 consistent, 2 inconsistent, 3 incomplete" in text
    assert "INCONSISTENT LEDGER_PAYOUT_MISMATCH" in text
    assert "INCOMPLETE FINAL_INTEREST_PENDING" in text
    assert "Read-only audit" in text

    other_out = StringIO()
    call_command("audit_fd_renewals", "--user-id", str(other_user.id), stdout=other_out)
    assert "No fixed deposit renewals matched" in other_out.getvalue()
    assert _snapshot(api_client) == before


@pytest.mark.django_db
def test_command_rejects_unknown_user(seeded):
    with pytest.raises(CommandError):
        call_command("audit_fd_renewals", "--user-id", "999999", stdout=StringIO())


# --- API --------------------------------------------------------------------


@pytest.mark.django_db
def test_api_returns_audit_without_changing_data(api_client, seeded, test_user):
    ids = _build_scenarios(api_client, test_user)
    before = _snapshot(api_client)

    with CaptureQueriesContext(connection) as ctx:
        response = api_client.get(AUDIT_URL)

    assert response.status_code == 200
    _assert_select_only(ctx.captured_queries)
    assert _snapshot(api_client) == before
    payload = response.json()
    _assert_expected(payload["results"], ids)
    assert payload["summary"]["finding_counts"]["FINAL_INTEREST_PENDING"] == 1
    partial = _by_old_fd(payload["results"])[ids["partial_rollover"]]
    assert partial["totals"]["cash_payout_recorded"] == 10000.0
    assert partial["totals"]["reinvested_interest"] == 0.0


@pytest.mark.django_db
def test_api_is_scoped_to_owner_and_portfolio(api_client, seeded, test_user, other_user):
    default = ensure_default_portfolio(test_user)
    second = Portfolio.objects.create(
        user=test_user, name="Second", base_currency="INR", is_active=True
    )
    fd_default = _quarterly_fd(test_user, default, "DEFAULT")
    _renew(api_client, fd_default)
    fd_second = _create_fd(
        test_user,
        second,
        bank=create_test_bank_account(test_user, portfolio=second, account_number="B-2"),
        deposit_account_number="SECOND",
        interest_payout_frequency="QUARTERLY",
    )
    _renew(api_client, fd_second)

    other_portfolio = Portfolio.objects.create(
        user=other_user, name="Other", base_currency="INR", is_active=True
    )
    other_fd = _create_fd(
        other_user,
        other_portfolio,
        bank=create_test_bank_account(other_user, portfolio=other_portfolio),
    )
    renew_fixed_deposit(
        other_user,
        other_fd.id,
        renewal_date=date(2026, 1, 1),
        new_deposit_account_number="OTHER-2",
        new_principal_amount=Decimal("100000"),
        new_interest_rate_percent=Decimal("7"),
        new_interest_payout_frequency="QUARTERLY",
        new_investment_date=date(2026, 1, 1),
        new_maturity_date=date(2027, 1, 1),
    )

    all_ids = {r["old_term"]["id"] for r in api_client.get(AUDIT_URL).json()["results"]}
    assert all_ids == {fd_default.id, fd_second.id}

    scoped = api_client.get(f"{AUDIT_URL}?portfolio_id={second.id}").json()
    assert [r["old_term"]["id"] for r in scoped["results"]] == [fd_second.id]

    dated = api_client.get(f"{AUDIT_URL}?start_date=2026-02-01").json()
    assert dated["results"] == []


@pytest.mark.django_db
def test_api_requires_authentication(anon_client, seeded):
    assert anon_client.get(AUDIT_URL).status_code in (401, 403)
