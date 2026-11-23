"""#44: pure FD renewal audit rules."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from finance.fd_renewal_audit import (
    LEG_INTEREST,
    LEG_PRINCIPAL,
    STATUS_CONSISTENT,
    STATUS_INCOMPLETE,
    STATUS_INCONSISTENT,
    LedgerMovement,
    PendingPayoutRecord,
    RenewalAuditInput,
    SettlementRecord,
    TermRef,
    audit_renewal,
    summarize_renewal_audit,
)

D = Decimal
OLD_ID, NEW_ID = 10, 11


def _term(id_, principal, *, status="MATURED_SETTLED", renewal_of=None, freq="QUARTERLY"):
    return TermRef(
        id=id_,
        deposit_account_number=f"FD-{id_}",
        institution_name="HDFC",
        status=status,
        principal_amount=D(principal),
        currency="INR",
        interest_payout_frequency=freq,
        renewal_of_id=renewal_of,
    )


def _movement(id_, amount, leg, *, direction="CREDIT", fd_id=OLD_ID, currency="INR"):
    return LedgerMovement(
        id=id_,
        leg=leg,
        direction=direction,
        amount=D(amount),
        currency=currency,
        movement_date=date(2026, 1, 1),
        linked_fixed_deposit_id=fd_id,
    )


def _renewal(
    *,
    old="100000",
    new="100000",
    payout="0",
    gross="0",
    tax="0",
    principal_mid=None,
    interest_mid=None,
    movements=(),
    pending=None,
    old_freq="QUARTERLY",
):
    net = D(gross) - D(tax)
    total = D(old) + net
    return RenewalAuditInput(
        renewal_id=1,
        renewal_date=date(2026, 1, 1),
        currency="INR",
        old_principal=D(old),
        direct_reinvest_amount=D(new),
        cash_payout_amount=D(payout),
        gross_interest=D(gross),
        tax_withheld=D(tax),
        net_interest=net,
        total_maturity_value=total,
        old_term=_term(OLD_ID, old, freq=old_freq),
        new_term=_term(NEW_ID, new, status="ACTIVE", renewal_of=OLD_ID),
        settlement=SettlementRecord(
            id=5,
            fixed_deposit_id=OLD_ID,
            settlement_date=date(2026, 1, 1),
            principal_returned=D(old),
            gross_interest=D(gross),
            tax_withheld=D(tax),
            net_interest=net,
            total_net_proceeds=total,
            principal_movement_id=principal_mid,
            interest_movement_id=interest_mid,
        ),
        movements=tuple(movements),
        pending_payout=pending,
    )


def _pending(status="PENDING", *, suggested="4500", net=None, mid=None, discrepancy="NONE"):
    return PendingPayoutRecord(
        id=7,
        status=status,
        suggested_net_interest=D(suggested) if suggested is not None else None,
        net_interest=D(net) if net is not None else None,
        payment_date=date(2026, 1, 12) if status == "CONFIRMED" else None,
        movement_id=mid,
        discrepancy_status=discrepancy,
        discrepancy_amount=None,
    )


def _codes(result):
    return [f.code for f in result.findings]


# --- consistent -------------------------------------------------------------


def test_full_rollover_with_reinvested_interest_is_consistent():
    result = audit_renewal(_renewal(new="104500", gross="5000", tax="500"))

    assert result.status == STATUS_CONSISTENT
    assert result.findings == ()
    assert result.totals.total_available == D("104500")
    assert result.totals.reinvested_interest == D("4500")
    assert result.totals.ledger_payout_total == D("0")


def test_partial_rollover_with_both_legs_is_consistent():
    result = audit_renewal(
        _renewal(
            new="94500",
            payout="10000",
            gross="5000",
            tax="500",
            principal_mid=1,
            interest_mid=2,
            movements=[_movement(1, "5500", LEG_PRINCIPAL), _movement(2, "4500", LEG_INTEREST)],
        )
    )

    assert result.status == STATUS_CONSISTENT
    assert result.totals.expected_interest_cash == D("4500")
    assert result.totals.expected_principal_cash == D("5500")
    assert result.settlement_movement_ids == (1, 2)


def test_confirmed_later_payout_matching_ledger_is_consistent():
    result = audit_renewal(
        _renewal(
            movements=[_movement(3, "4500", LEG_INTEREST)],
            pending=_pending("CONFIRMED", net="4500", mid=3),
        )
    )

    assert result.status == STATUS_CONSISTENT
    assert result.totals.confirmed_later_payout_net == D("4500")
    assert result.totals.pending_estimate_net == D("0")
    assert result.unlinked_movement_ids == ()


# --- inconsistent -----------------------------------------------------------


def test_allocation_gap_is_inconsistent_with_reason():
    result = audit_renewal(_renewal(new="100000", gross="5000", tax="500"))

    assert result.status == STATUS_INCONSISTENT
    assert _codes(result) == ["ALLOCATION_MISMATCH"]
    assert "gap INR 4,500.00" in result.findings[0].message
    assert result.totals.allocation_gap == D("4500")
    assert result.totals.reinvested_interest is None


def test_reinvesting_pending_estimate_is_flagged_as_not_settled():
    result = audit_renewal(_renewal(new="104500", pending=_pending()))

    assert result.status == STATUS_INCONSISTENT
    assert "ALLOCATION_MISMATCH" in _codes(result)
    assert "FINAL_INTEREST_PENDING" in _codes(result)
    message = next(f.message for f in result.findings if f.code == "ALLOCATION_MISMATCH")
    assert "pending interest estimate" in message
    assert result.totals.net_interest == D("0")
    assert result.totals.pending_estimate_net == D("4500")


def test_legacy_interest_credit_on_full_rollover_is_ledger_mismatch():
    result = audit_renewal(
        _renewal(
            new="104500",
            gross="5000",
            tax="500",
            interest_mid=2,
            movements=[_movement(2, "4500", LEG_INTEREST)],
        )
    )

    assert result.status == STATUS_INCONSISTENT
    assert _codes(result) == ["LEDGER_PAYOUT_MISMATCH"]
    assert result.totals.ledger_payout_total == D("4500")
    assert result.totals.cash_payout_recorded == D("0")


def test_leg_split_against_rules_is_inconsistent():
    result = audit_renewal(
        _renewal(
            new="94500",
            payout="10000",
            gross="5000",
            tax="500",
            principal_mid=1,
            movements=[_movement(1, "10000", LEG_PRINCIPAL)],
        )
    )

    assert result.status == STATUS_INCONSISTENT
    assert _codes(result) == ["LEDGER_SPLIT_MISMATCH"]


def test_term_and_settlement_disagreements_are_inconsistent():
    base = _renewal(new="104500", gross="5000", tax="500")
    audit = replace(
        base,
        old_term=replace(base.old_term, principal_amount=D("99000"), status="ACTIVE"),
        new_term=replace(base.new_term, principal_amount=D("104000"), renewal_of_id=None),
        settlement=replace(base.settlement, net_interest=D("4000")),
    )

    result = audit_renewal(audit)

    assert result.status == STATUS_INCONSISTENT
    assert set(_codes(result)) == {
        "OLD_PRINCIPAL_MISMATCH",
        "REINVESTED_PRINCIPAL_MISMATCH",
        "TERM_LINK_MISMATCH",
        "TERM_STATUS_MISMATCH",
        "SETTLEMENT_MISMATCH",
    }


def test_interest_recorded_on_renewal_and_payout_is_double_recorded():
    result = audit_renewal(
        _renewal(
            new="104500",
            gross="5000",
            tax="500",
            movements=[_movement(3, "4500", LEG_INTEREST)],
            pending=_pending("CONFIRMED", net="4500", mid=3),
        )
    )

    assert "FINAL_INTEREST_DOUBLE_RECORDED" in _codes(result)
    assert result.status == STATUS_INCONSISTENT


def test_confirmed_payout_credit_amount_mismatch_is_inconsistent():
    result = audit_renewal(
        _renewal(
            movements=[_movement(3, "4000", LEG_INTEREST)],
            pending=_pending("CONFIRMED", net="4500", mid=3),
        )
    )

    assert _codes(result) == ["CONFIRMED_PAYOUT_LEDGER_MISMATCH"]


def test_referenced_credit_linked_elsewhere_is_inconsistent():
    result = audit_renewal(
        _renewal(
            new="90000",
            payout="10000",
            principal_mid=1,
            movements=[_movement(1, "10000", LEG_PRINCIPAL, fd_id=99)],
        )
    )

    assert _codes(result) == ["LEDGER_LINK_MISMATCH"]


# --- incomplete -------------------------------------------------------------


def test_pending_final_interest_is_incomplete_and_not_settled():
    result = audit_renewal(_renewal(pending=_pending()))

    assert result.status == STATUS_INCOMPLETE
    assert _codes(result) == ["FINAL_INTEREST_PENDING"]
    assert result.totals.net_interest == D("0")
    assert result.totals.total_available == D("100000")
    assert result.totals.pending_estimate_net == D("4500")


def test_payout_without_linked_credit_is_incomplete():
    result = audit_renewal(_renewal(new="90000", payout="10000"))

    assert result.status == STATUS_INCOMPLETE
    assert _codes(result) == ["MISSING_PAYOUT_MOVEMENTS"]


def test_unlinked_maturity_credit_is_ambiguous():
    result = audit_renewal(
        _renewal(new="90000", payout="10000", movements=[_movement(9, "10000", LEG_PRINCIPAL)])
    )

    assert result.status == STATUS_INCOMPLETE
    assert _codes(result) == ["MISSING_PAYOUT_MOVEMENTS", "UNLINKED_MATURITY_MOVEMENT"]
    assert result.unlinked_movement_ids == (9,)
    assert result.totals.unlinked_movement_total == D("10000")


def test_missing_settlement_is_incomplete():
    result = audit_renewal(replace(_renewal(), settlement=None))

    assert result.status == STATUS_INCOMPLETE
    assert _codes(result) == ["MISSING_SETTLEMENT"]


def test_open_discrepancy_and_missing_payout_credit_are_incomplete():
    result = audit_renewal(
        _renewal(pending=_pending("CONFIRMED", net="4000", mid=None, discrepancy="OPEN"))
    )

    assert result.status == STATUS_INCOMPLETE
    assert _codes(result) == ["CONFIRMED_PAYOUT_MOVEMENT_MISSING", "PAYOUT_DISCREPANCY_OPEN"]


def test_cumulative_term_renewed_without_interest_is_incomplete():
    result = audit_renewal(_renewal(old_freq="COMPOUNDED"))

    assert result.status == STATUS_INCOMPLETE
    assert _codes(result) == ["NO_FINAL_INTEREST_RECORDED"]


def test_inconsistent_outranks_incomplete():
    result = audit_renewal(_renewal(new="104500", pending=_pending()))

    assert {f.kind for f in result.findings} == {STATUS_INCONSISTENT, STATUS_INCOMPLETE}
    assert result.status == STATUS_INCONSISTENT


# --- summary ----------------------------------------------------------------


def test_summary_counts_and_keeps_currencies_separate():
    consistent = audit_renewal(_renewal(new="104500", gross="5000", tax="500"))
    pending = audit_renewal(_renewal(pending=_pending()))
    usd_input = _renewal(old="1000", new="1000")
    usd = audit_renewal(
        replace(
            usd_input,
            currency="USD",
            old_term=replace(usd_input.old_term, currency="USD"),
            new_term=replace(usd_input.new_term, currency="USD"),
        )
    )

    summary = summarize_renewal_audit([consistent, pending, usd])

    assert summary.renewal_count == 3
    assert summary.status_counts == {
        STATUS_CONSISTENT: 2,
        STATUS_INCONSISTENT: 0,
        STATUS_INCOMPLETE: 1,
    }
    assert summary.finding_counts == {"FINAL_INTEREST_PENDING": 1}
    inr, usd_totals = summary.totals_by_currency
    assert (inr.currency, inr.renewal_count) == ("INR", 2)
    assert inr.old_principal == D("200000")
    assert inr.net_interest == D("4500")
    assert inr.pending_estimate_net == D("4500")
    assert (usd_totals.currency, usd_totals.old_principal) == ("USD", D("1000"))
