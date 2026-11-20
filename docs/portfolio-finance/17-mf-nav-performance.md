# Mutual-fund NAV performance and personal position

Implemented under specification #3 and phases #4 through #10. These requirements
supersede the historical MF-5 use of personal cash flows for fund-level metrics;
they do not change portfolio cash-flow-adjusted analytics.

## Three different subjects

| Subject | Inputs and currency |
|---|---|
| Fund Performance | Cached positive NAV observations, native INR; no personal trades or FX |
| Your Position | Recorded holdings, FIFO basis and selected display currency |
| Portfolio performance | Portfolio value and external cash flows, preserving existing mode-specific behavior |

Asset Detail and Compare use the same fund series. Folio and portfolio selectors
still enforce existing authorization and personal context, but do not filter the
fund's NAV history. A user still needs existing authorized asset access. Multiple
folios do not require choosing one merely to calculate fund performance.

## Return and coverage contract

- Successive eligible NAV observations produce fractional returns. Cash flows,
  units and payment/NAV date differences do not enter the fund-return calculation.
- Cumulative return and NAV-chain return compound that series. CAGR uses actual
  elapsed dates including the eligible opening predecessor. Risk statistics reuse
  the established observation-return helpers and their 252-observation annualization.
- Bounded periods load a preceding cached NAV for opening comparisons, without
  emitting an out-of-range return. ALL uses available cached fund history, not the
  first personal purchase; it is not a guarantee of full scheme-launch history.
- Normal non-publication dates do not create daily observations or invented zero
  returns. A gap greater than seven calendar days is ineligible for chaining.
  No interpolation, future NAV substitution or zero-valued missing NAV is used.
- Missing opening coverage and stale endpoints are explicit. Aggregate fund
  metrics and drawdown series are unavailable for incomplete coverage. Monthly or
  yearly rows intersecting an unexplained gap are omitted, so clients show missing
  values rather than a fabricated zero. Coverage metadata records partial periods;
  the UI uses ordinary period labels and actual NAV coverage dates, without
  "Partial" badges or qualifiers, per the user's presentation preference.
- Benchmark statistics require a configured INR benchmark and eligible overlapping
  observation intervals. Align prices/NAVs first, then calculate both returns;
  intersecting already-calculated return dates can silently drop real gains.
  Shared predecessors are selected before bounded-range trimming. Missing or
  currency-incompatible benchmarks produce warnings; benchmark gaps remain explicit
  even when enough valid intervals survive to calculate partial statistics.
  Compare subjects identify their currency/basis; mixed-currency normalized
  comparisons are unavailable rather than silently mixing INR and EUR returns.
- No provider requests or persistence writes occur during analytics reads. Full
  scheme history must be populated by an explicit cache-refresh workflow.

## Additive API metadata

MF asset analytics and MF Compare subjects add `performance_basis: nav`,
`currency: INR`, and `coverage` with actual start/end, requested start, incomplete
status, gap intervals, partial months and partial years. Existing return/risk/
drawdown/period keys remain, but now describe the fund, not the investor.

`metrics.return.xirr` is unavailable for fund NAV performance. Personal XIRR
is returned separately under `personal_metrics` with `xirr_scope: full_scope`,
`basis: native_inr` and status `calculated` or `unavailable`. The Asset Detail
position header, holdings, Metric Sheet and Compare use the same calculation
for the same position scope. It uses investment dates and recorded payments or
net redemption proceeds, with remaining units valued at the latest cached NAV
dated on or before the valuation date (`portfolios.dates.current_date()`).
NAV rows after that date are ignored. An open position with no eligible NAV is
unavailable (never zero-valued or future-valued). A fully redeemed position may
still compute from realized cash flows without a terminal NAV. Display currency
has no effect on this INR return.

When cash flows have no solvable annualized rate (for example equal payments and
receipts on the same day with no remaining units), personal XIRR is unavailable,
not zero. HTTP regressions cover this state and future-NAV exclusion consistently
across holdings, Asset Detail, Metric Sheet and Compare.

Cumulative NAV Return and TWROR are the same compounded NAV measure on this
surface because personal cash flows are outside the fund NAV series. The UI shows
one return card; API consumers retain both existing fields.

## Timing bug diagnosis

The previous fund heatmap mixed an investment-date cash flow with NAV-date unit
recognition. A payment could therefore appear as a large loss before the units
arrived, followed by a false gain. Compounding those percentages does not cancel
the artifact. The correction is NAV-only fund performance, not rewriting payment
dates or shifting the user's portfolio deposits. Reload Asset Detail after the
backend reloads. Missing cache coverage still needs an explicit NAV refresh, not
zero-filled return values.

## Historical personal XIRR audit

The legacy MF Metric Sheet invokes a helper whose default calculation currency is
EUR. Payments are converted to EUR while its supplied terminal value remains INR.
A synthetic 958-day investment of INR 10,000 with terminal INR 11,808.95303866 and
EUR 1 = INR 90 produces about 491.67% in that path, versus 6.54% using consistent
native currency. The existing position-header path instead uses NAV dates and
reconstructed unit-price cash flows, not the actual payment dates and paid values.
It therefore is not an automatically valid reference answer either.

The shared native-INR holding calculation replaces those two legacy estimates.
It does not rewrite payment dates or change portfolio XIRR.

## Portfolio timing audit: correction requires separate approval

The same payment/unit-recognition mismatch exists in portfolio valuation. In a
constant-NAV synthetic legacy portfolio with opening holdings 1,000 and a purchase
of 500 paid before unit recognition, daily returns are -50% then +50%, leaving an
artificial -25% compounded return. A payment-first sale has the same failure.

Cash-aware portfolios also temporarily omit or double-count unsettled investment
value. With opening holdings 1,000 and cash 1,000, a purchase of 500 paid before
unit recognition gives -25% then +33.33%: settled TWROR recovers, but risk metrics
and period boundaries remain distorted. Full-capital zero-value cases can retain
a spurious loss. Same-day controls do not have these timing artifacts.

No pending-investment/redemption model or portfolio financial correction is part
of this release. A separate proposal must cover both date orders, purchases,
sales, first funding, full liquidation and period boundaries before approval.

## Acceptance and data safety

Pinned March NAV endpoints 481.392 and 484.131 imply approximately +0.568975%.
Personal purchases must not change that return. Synthetic fixtures, rather than
live portfolio mutations or network-dependent tests, establish the regression.

Tests use SQLite for backend HTTP behavior and rendered frontend components for
labels and currency separation. No database migrations or transaction/ledger
backfills are required. KPulla5 is unchanged.
