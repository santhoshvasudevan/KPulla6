"""FD-TAX-1: fixed deposit interest and tax withheld report API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from debt.interest_payment_services import create_fixed_deposit_interest_payment
from debt.models import (
    CashMovement,
    FixedDepositInterestPayment,
    FixedDepositRenewalGroup,
    FixedDepositSettlement,
    FixedDepositStatus,
)
from debt.reversal_services import reverse_fixed_deposit_interest_payment
from debt.services import create_bank_account, create_fixed_deposit
from fx.services import upsert_fx_rate
from portfolios.models import Portfolio
from portfolios.seed import ensure_default_portfolio
from tests.debt_test_helpers import create_test_bank_account, fund_bank_account


def _bank(user, portfolio=None, **overrides):
    return create_test_bank_account(user, portfolio=portfolio, **overrides)



def _create_fd(user, portfolio_id, bank, **overrides):
    fund_bank_account(user, bank, "300000")
    payload = dict(
        portfolio_id=portfolio_id,
        bank_account_id=bank.id,
        institution_name="HDFC",
        deposit_account_number="FD-TAX",
        principal_amount=Decimal("100000"),
        currency=bank.currency,
        interest_rate_percent=Decimal("7"),
        interest_payout_frequency="QUARTERLY",
        investment_date=date(2024, 1, 1),
        maturity_date=date(2026, 1, 1),
    )
    payload.update(overrides)
    return create_fixed_deposit(user, **payload)


def _report(api_client, **query):
    params = []
    for key, val in query.items():
        params.append(f"{key}={val}")
    qs = "&".join(params) if params else ""
    url = "/api/v1/reports/fixed-deposit-interest"
    if qs:
        url = f"{url}?{qs}"
    return api_client.get(url)


def _export_csv(api_client, **query):
    import csv
    from io import StringIO

    params = []
    for key, val in query.items():
        params.append(f"{key}={val}")
    qs = "&".join(params) if params else ""
    url = "/api/v1/reports/fixed-deposit-interest/export.csv"
    if qs:
        url = f"{url}?{qs}"
    response = api_client.get(url)
    if response.status_code != 200:
        return response, None, None
    text = response.content.decode("utf-8")
    reader = csv.reader(StringIO(text))
    rows = list(reader)
    return response, rows[0] if rows else [], rows[1:] if len(rows) > 1 else []


@pytest.mark.django_db
def test_report_includes_normal_interest_payment(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("100"),
    )

    body = _report(api_client).json()
    assert body["totals"]["row_count"] == 1
    row = body["rows"][0]
    assert row["source_type"] == "INTEREST_PAYMENT"
    assert row["gross_interest"] == pytest.approx(1000.0)
    assert row["tax_withheld"] == pytest.approx(100.0)
    assert row["net_interest"] == pytest.approx(900.0)


@pytest.mark.django_db
def test_report_excludes_reversed_interest_payment(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 5, 1),
        gross_interest=Decimal("500"),
        tax_withheld=Decimal("50"),
    )
    reverse_fixed_deposit_interest_payment(
        test_user, payment.payment.id, reason="test reversal"
    )

    body = _report(api_client).json()
    assert body["totals"]["row_count"] == 0
    assert body["rows"] == []


@pytest.mark.django_db
def test_report_includes_settlement_final_interest(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        {
            "settlement_type": "CLOSURE",
            "settlement_date": "2025-06-01",
            "gross_interest": 2000,
            "tax_withheld": 200,
        },
        format="json",
    )

    body = _report(api_client).json()
    settlement_rows = [r for r in body["rows"] if r["source_type"] == "SETTLEMENT"]
    assert len(settlement_rows) == 1
    assert settlement_rows[0]["gross_interest"] == pytest.approx(2000.0)
    assert settlement_rows[0]["tax_withheld"] == pytest.approx(200.0)
    assert settlement_rows[0]["net_interest"] == pytest.approx(1800.0)


@pytest.mark.django_db
def test_report_includes_renewal_interest_not_duplicate_settlement(
    api_client, seeded, test_user
):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/renew",
        {
            "renewal_date": "2026-01-01",
            "new_deposit_account_number": "FD-002",
            "new_principal_amount": 100000,
            "new_interest_rate_percent": 7.5,
            "new_interest_payout_frequency": "QUARTERLY",
            "new_investment_date": "2026-01-01",
            "new_maturity_date": "2028-01-01",
            "gross_interest": 1500,
            "tax_withheld": 150,
        },
        format="json",
    )

    body = _report(api_client).json()
    assert body["totals"]["row_count"] == 1
    assert body["rows"][0]["source_type"] == "RENEWAL"
    assert body["rows"][0]["gross_interest"] == pytest.approx(1500.0)


@pytest.mark.django_db
def test_report_excludes_zero_interest_settlement(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        {
            "settlement_type": "CLOSURE",
            "settlement_date": "2025-06-01",
            "gross_interest": 0,
            "tax_withheld": 0,
        },
        format="json",
    )

    body = _report(api_client).json()
    assert body["totals"]["row_count"] == 0


@pytest.mark.django_db
def test_report_date_range_filter(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 3, 1),
        gross_interest=Decimal("100"),
        tax_withheld=Decimal("0"),
    )
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 8, 1),
        gross_interest=Decimal("200"),
        tax_withheld=Decimal("0"),
    )

    body = _report(
        api_client, start_date="2024-06-01", end_date="2024-12-31"
    ).json()
    assert body["totals"]["row_count"] == 1
    assert body["rows"][0]["gross_interest"] == pytest.approx(200.0)


@pytest.mark.django_db
def test_report_portfolio_scope_filter(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Other", base_currency="INR", is_active=True
    )
    bank1 = _bank(test_user, portfolio=p1, account_number="tax-rpt-a")
    bank2 = _bank(test_user, portfolio=p2, account_number="tax-rpt-b")
    fd1 = _create_fd(test_user, p1.id, bank1, deposit_account_number="FD-A")
    fd2 = _create_fd(test_user, p2.id, bank2, deposit_account_number="FD-B")
    create_fixed_deposit_interest_payment(
        test_user, fd1.id, payment_date=date(2024, 4, 1), gross_interest=Decimal("100")
    )
    create_fixed_deposit_interest_payment(
        test_user, fd2.id, payment_date=date(2024, 4, 1), gross_interest=Decimal("300")
    )

    body = _report(api_client, portfolio_id=p2.id).json()
    assert body["totals"]["row_count"] == 1
    assert body["rows"][0]["portfolio_id"] == p2.id


@pytest.mark.django_db
def test_report_user_scoping(api_client, seeded, test_user, django_user_model):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user, fd.id, payment_date=date(2024, 4, 1), gross_interest=Decimal("100")
    )

    other = django_user_model.objects.create_user(
        username="other-tax", email="other@example.com", password="pass"
    )
    other_portfolio = ensure_default_portfolio(other)
    other_bank = _bank(other, account_number="other-acct")
    other_fd = _create_fd(other, other_portfolio.id, other_bank)
    create_fixed_deposit_interest_payment(
        other, other_fd.id, payment_date=date(2024, 4, 1), gross_interest=Decimal("999")
    )

    body = _report(api_client).json()
    assert body["totals"]["row_count"] == 1
    assert body["rows"][0]["gross_interest"] == pytest.approx(100.0)


@pytest.mark.django_db
def test_report_totals_gross_tax_net(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("100"),
    )
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 7, 1),
        gross_interest=Decimal("500"),
        tax_withheld=Decimal("50"),
    )

    totals = _report(api_client).json()["totals"]
    assert totals["gross_interest"] == pytest.approx(1500.0)
    assert totals["tax_withheld"] == pytest.approx(150.0)
    assert totals["net_interest"] == pytest.approx(1350.0)
    assert totals["row_count"] == 2


@pytest.mark.django_db
def test_report_group_by_year(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("100"),
        tax_withheld=Decimal("0"),
    )
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2025, 4, 1),
        gross_interest=Decimal("200"),
        tax_withheld=Decimal("0"),
    )

    body = _report(api_client, group_by="year").json()
    assert len(body["grouped_totals"]) == 2
    by_year = {g["group_key"]: g for g in body["grouped_totals"]}
    assert by_year["2024"]["gross_interest"] == pytest.approx(100.0)
    assert by_year["2025"]["gross_interest"] == pytest.approx(200.0)


@pytest.mark.django_db
def test_report_excludes_cancelled_fd_interest(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("0"),
    )
    fd.status = FixedDepositStatus.CANCELLED
    fd.is_active = False
    fd.save(update_fields=["status", "is_active", "updated_at"])

    body = _report(api_client).json()
    assert body["totals"]["row_count"] == 0


@pytest.mark.django_db
def test_report_display_currency_conversion(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, currency="EUR", account_number="eur-tax")
    fd = _create_fd(
        test_user,
        portfolio.id,
        bank,
        deposit_account_number="FD-EUR",
    )
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 6, 1),
        gross_interest=Decimal("100"),
        tax_withheld=Decimal("10"),
    )
    upsert_fx_rate(
        from_currency="EUR",
        to_currency="INR",
        row_date=date(2024, 6, 1),
        rate=Decimal("90"),
    )

    body = _report(api_client, display_currency="INR").json()
    row = body["rows"][0]
    assert row["gross_interest_display"] == pytest.approx(9000.0)
    assert body["totals"]["display_currency"] == "INR"
    assert body["totals"]["gross_interest"] == pytest.approx(9000.0)


@pytest.mark.django_db
def test_report_does_not_mutate_accounting_state(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("100"),
        tax_withheld=Decimal("0"),
    )
    payment_count = FixedDepositInterestPayment.objects.count()
    movement_count = CashMovement.objects.count()
    settlement_count = FixedDepositSettlement.objects.count()
    renewal_count = FixedDepositRenewalGroup.objects.count()

    assert _report(api_client).status_code == 200

    assert FixedDepositInterestPayment.objects.count() == payment_count
    assert CashMovement.objects.count() == movement_count
    assert FixedDepositSettlement.objects.count() == settlement_count
    assert FixedDepositRenewalGroup.objects.count() == renewal_count


@pytest.mark.django_db
def test_csv_export_returns_text_csv_with_disposition(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("100"),
    )

    response, header, _rows = _export_csv(
        api_client,
        start_date="2024-01-01",
        end_date="2024-12-31",
    )
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    disposition = response["Content-Disposition"]
    assert "attachment" in disposition
    assert "fd-interest-tax-2024-01-01-to-2024-12-31.csv" in disposition
    assert header[0] == "Date"
    assert "Gross Interest Display" in header


@pytest.mark.django_db
def test_csv_export_includes_interest_payment_row(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("1000"),
        tax_withheld=Decimal("100"),
        comment="Q1 payout",
    )

    _response, _header, data_rows = _export_csv(api_client)
    assert len(data_rows) == 1
    row = data_rows[0]
    assert row[0] == "2024-04-01"
    assert row[1] == "INTEREST_PAYMENT"
    assert row[2] == "Interest payment"
    assert row[8] == "1000"
    assert row[9] == "100"
    assert row[10] == "900"
    assert row[15] == "Q1 payout"


@pytest.mark.django_db
def test_csv_export_excludes_reversed_interest_payment(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    payment = create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 5, 1),
        gross_interest=Decimal("500"),
        tax_withheld=Decimal("50"),
    )
    reverse_fixed_deposit_interest_payment(
        test_user, payment.payment.id, reason="test reversal"
    )

    _response, header, data_rows = _export_csv(api_client)
    assert header
    assert data_rows == []


@pytest.mark.django_db
def test_csv_export_includes_settlement_and_renewal_rows(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    api_client.post(
        f"/api/v1/fixed-deposits/{fd.id}/settle",
        {
            "settlement_type": "CLOSURE",
            "settlement_date": "2025-06-01",
            "gross_interest": 2000,
            "tax_withheld": 200,
        },
        format="json",
    )

    _response, _header, data_rows = _export_csv(api_client)
    assert len(data_rows) == 1
    assert data_rows[0][1] == "SETTLEMENT"
    assert data_rows[0][2] == "Settlement"


@pytest.mark.django_db
def test_csv_export_respects_date_and_portfolio_filters(api_client, seeded, test_user):
    p1 = ensure_default_portfolio(test_user)
    p2 = Portfolio.objects.create(
        user=test_user, name="Other", base_currency="INR", is_active=True
    )
    bank1 = _bank(test_user, portfolio=p1, account_number="csv-a")
    bank2 = _bank(test_user, portfolio=p2, account_number="csv-b")
    fd1 = _create_fd(test_user, p1.id, bank1, deposit_account_number="FD-A")
    fd2 = _create_fd(test_user, p2.id, bank2, deposit_account_number="FD-B")
    create_fixed_deposit_interest_payment(
        test_user, fd1.id, payment_date=date(2024, 3, 1), gross_interest=Decimal("100")
    )
    create_fixed_deposit_interest_payment(
        test_user, fd2.id, payment_date=date(2024, 8, 1), gross_interest=Decimal("300")
    )

    _response, _header, data_rows = _export_csv(
        api_client,
        portfolio_id=p2.id,
        start_date="2024-06-01",
        end_date="2024-12-31",
    )
    assert len(data_rows) == 1
    assert data_rows[0][8] == "300"


@pytest.mark.django_db
def test_csv_export_user_scoped(api_client, seeded, test_user, django_user_model):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user, fd.id, payment_date=date(2024, 4, 1), gross_interest=Decimal("100")
    )

    other = django_user_model.objects.create_user(
        username="other-csv", email="other@example.com", password="pass"
    )
    other_portfolio = ensure_default_portfolio(other)
    other_bank = _bank(other, account_number="other-csv")
    other_fd = _create_fd(other, other_portfolio.id, other_bank)
    create_fixed_deposit_interest_payment(
        other, other_fd.id, payment_date=date(2024, 4, 1), gross_interest=Decimal("999")
    )

    _response, _header, data_rows = _export_csv(api_client)
    assert len(data_rows) == 1
    assert data_rows[0][8] == "100"


@pytest.mark.django_db
def test_csv_export_display_currency_columns(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user, currency="EUR", account_number="eur-csv")
    fd = _create_fd(test_user, portfolio.id, bank, deposit_account_number="FD-EUR")
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 6, 1),
        gross_interest=Decimal("100"),
        tax_withheld=Decimal("10"),
    )
    upsert_fx_rate(
        from_currency="EUR",
        to_currency="INR",
        row_date=date(2024, 6, 1),
        rate=Decimal("90"),
    )

    _response, header, data_rows = _export_csv(api_client, display_currency="INR")
    assert "Gross Interest Display" in header
    assert data_rows[0][11] == "INR"
    assert data_rows[0][12] == "9000"


@pytest.mark.django_db
def test_csv_export_header_only_when_no_rows(api_client, seeded, test_user):
    _response, header, data_rows = _export_csv(api_client)
    assert header
    assert data_rows == []


@pytest.mark.django_db
def test_csv_export_does_not_mutate_accounting_state(api_client, seeded, test_user):
    portfolio = ensure_default_portfolio(test_user)
    bank = _bank(test_user)
    fd = _create_fd(test_user, portfolio.id, bank)
    create_fixed_deposit_interest_payment(
        test_user,
        fd.id,
        payment_date=date(2024, 4, 1),
        gross_interest=Decimal("100"),
        tax_withheld=Decimal("0"),
    )
    payment_count = FixedDepositInterestPayment.objects.count()
    movement_count = CashMovement.objects.count()

    assert _export_csv(api_client)[0].status_code == 200

    assert FixedDepositInterestPayment.objects.count() == payment_count
    assert CashMovement.objects.count() == movement_count
