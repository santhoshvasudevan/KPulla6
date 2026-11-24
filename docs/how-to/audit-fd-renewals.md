# Audit fixed deposit renewals

Check recorded FD renewals against the direct-renewal rules (#43) before comparing them with bank statements (#44). The audit is **read-only**: it never repairs records, backfills the ledger, or posts bank movements. Corrections are a separate, explicitly approved action.

## What is compared

For each `FixedDepositRenewalGroup` the audit reads the renewed (old) term, the successor term, the settlement, bank movements linked to the old term, and any final maturity payout (#45/#46):

| Recorded | Compared with |
|----------|---------------|
| Old principal + final net interest (gross − tax) | Reinvested principal + cash payout (`old principal + net interest = new principal + cash payout`) |
| Renewal old principal / reinvested principal | Old term principal / successor term principal |
| Renewal gross, tax, net, maturity total | Settlement figures for the old term |
| Recorded cash payout | Bank credits referenced by the settlement (interest leg first, then principal) |
| Confirmed final payout net | Its linked bank credit |

**Pending estimates are never settled proceeds.** A pending payout's suggested interest is shown separately (`pending_estimate_net`) and is excluded from the available amount.

## Run the command

```bash
cd backend
python manage.py audit_fd_renewals                 # all users, text report
python manage.py audit_fd_renewals --user-id 1     # one user
python manage.py audit_fd_renewals --json          # full report as JSON
```

The command only issues read queries and runs inside a transaction that is always rolled back. Even so, follow [Data safety](../data-safety.md) when pointing it at the live dev database; tests use SQLite only.

## Use the API

```http
GET /api/v1/reports/fixed-deposit-renewal-audit
GET /api/v1/reports/fixed-deposit-renewal-audit?portfolio_id=3
GET /api/v1/reports/fixed-deposit-renewal-audit?start_date=2025-04-01&end_date=2026-03-31
```

Authenticated owner only; renewals are scoped by the old term's portfolio (`portfolio_scope=all` default) and filtered on `renewal_date`. Amounts are always native currency; `display_currency` and `group_by` do not apply.

## Interpret the results

Each renewal gets one status:

| Status | Meaning | Next step |
|--------|---------|-----------|
| `CONSISTENT` | Recorded amounts and linked bank credits agree with the renewal rules | Compare totals with the bank statement |
| `INCONSISTENT` | The recorded data contradicts itself — a confirmed problem | Decide on a correction (separate approved action) |
| `INCOMPLETE` | No contradiction found, but evidence is missing or ambiguous | Find the missing evidence (statement, payout confirmation) |

`INCONSISTENT` outranks `INCOMPLETE` when a renewal has both kinds of finding. Every finding has a `code`, its `kind`, and a message with the amounts involved.

**Confirmed inconsistencies**

| Code | Reason |
|------|--------|
| `ALLOCATION_MISMATCH` | Old principal + net interest ≠ reinvested principal + cash payout (message notes when the gap equals a pending estimate) |
| `LEDGER_PAYOUT_MISMATCH` | Linked settlement bank credits ≠ recorded cash payout (typical of pre-#43 renewals that credited interest that was also reinvested) |
| `LEDGER_SPLIT_MISMATCH` | Total matches, but the interest/principal legs differ from the rule (interest first, then principal) |
| `OLD_PRINCIPAL_MISMATCH` / `REINVESTED_PRINCIPAL_MISMATCH` | Renewal amounts differ from the old or successor term principal |
| `SETTLEMENT_MISMATCH` | Settlement principal, gross, tax, net, or total differs from the renewal |
| `INTEREST_BREAKDOWN_MISMATCH` / `MATURITY_TOTAL_MISMATCH` | Gross − tax ≠ net, or maturity total ≠ old principal + net |
| `FINAL_INTEREST_DOUBLE_RECORDED` | Final interest recorded on the renewal and again as a maturity payout |
| `CONFIRMED_PAYOUT_LEDGER_MISMATCH` | A confirmed payout's bank credit differs from its net |
| `LEDGER_LINK_MISMATCH` | A referenced bank movement is not a credit, is in another currency, or is linked to another term |
| `TERM_LINK_MISMATCH` / `TERM_STATUS_MISMATCH` / `CURRENCY_MISMATCH` | Broken successor link, predecessor not completed, or currency differs |

**Missing or ambiguous evidence**

| Code | Reason |
|------|--------|
| `FINAL_INTEREST_PENDING` | Final interest awaits bank confirmation; the estimate is not counted |
| `PAYOUT_DISCREPANCY_OPEN` | Confirmed payout differs from its estimate and has not been reviewed (#46) |
| `MISSING_PAYOUT_MOVEMENTS` | A cash payout is recorded but no bank credit is linked to the settlement |
| `UNLINKED_MATURITY_MOVEMENT` | A maturity credit on the old term is not referenced by its settlement or payout |
| `CONFIRMED_PAYOUT_MOVEMENT_MISSING` | A confirmed payout with net > 0 has no bank credit |
| `NO_FINAL_INTEREST_RECORDED` | A cumulative term was renewed with no final interest and no pending payout |
| `MISSING_SETTLEMENT` | No settlement found for the renewed term |

**Reviewable totals** per renewal: `old_principal`, `gross_interest`, `tax_withheld`, `net_interest`, `total_available`, `reinvested_principal`, `cash_payout_recorded`, `allocation_gap`, the expected interest/principal cash split and `reinvested_interest` (null when the allocation fails), `ledger_payout_total` with interest/principal legs, `unlinked_movement_total`, `pending_estimate_net`, and `confirmed_later_payout_net`. Term references include both term ids, deposit numbers, statuses, portfolio and bank account ids, the settlement id, movement ids, and the payout id. The summary adds status and finding counts plus per-currency totals (currencies are never mixed).

## Verify

- `make test-backend` covers consistent, inconsistent, and incomplete scenarios and asserts records, balances, cash movements, and reports are identical before and after each audit run (`backend/tests/test_fixed_deposit_renewal_audit.py`).

## Related

- [FD accounting](../fixed-deposits-accounting.md) · [Fixed deposits](../fixed-deposits.md) · [Data safety](../data-safety.md)
