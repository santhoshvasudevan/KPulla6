# 015 — FD-PERF-2: Portfolio-attributed FD payout income for performance metrics

| Field | Value |
|-------|--------|
| **ID** | FD-PERF-2 |
| **Branch** | `agent/015-fd-perf-2` |
| **Status** | **Done** |
| **Depends on** | FD-PERF-1-DIAG (diagnostic) |
| **Epic** | Fixed Deposits / performance |

## Goal

Count recorded **payout FD interest** as portfolio income/return for the FD’s portfolio even when the receiving bank account is external or excluded from portfolio value. Bank account is only the credit destination; attribution comes from `FixedDeposit.portfolio`.

## Product rules

- Performance uses **net interest** (`net_interest`); gross/tax remain in FD detail/tax reports.
- **Anti-double-count:** when receiving bank is included in scope PV, do not add attributed income again.
- **Value metric (`metric=value`)** unchanged — headline wealth = principal + included bank cash only.
- **Return metrics** (`twror`, `cumulative_return`, XIRR) include attributed payout income when bank excluded.
- **Compounded FD** daily accrual and **gross-of-tax** performance mode remain deferred.

## Implementation

- `backend/debt/fd_attributed_income.py` — `FdAttributedIncomeEvent`, `list_fd_attributed_income_events`, `merge_fd_attributed_income_into_return_timeseries`, `build_fd_attributed_xirr_flows`.
- `portfolios/performance_service.build_return_value_timeseries` — cumulative attributed income on return PV series only.
- `portfolios/xirr_service._portfolio_xirr_inputs` — positive XIRR flows on payment dates when bank excluded.

## Tests

- `tests/test_fd_attributed_income.py`
- Existing FD performance tests unchanged for value metric; return behavior updated.

## Deferred

- Compounded FD daily accrual in PV/returns
- Gross-of-tax performance mode
- Broker-funded FD / broker-bank transfer
