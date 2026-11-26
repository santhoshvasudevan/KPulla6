import { useMemo } from 'react';
import CashFutureImpactDisplay from './CashFutureImpactDisplay';
import './CashFutureImpactDisplay.css';
import { Button, WarningBanner } from './ui';

const BANK_FUTURE_IMPACT_HELPER =
  'Add another bank deposit, edit later withdrawals, or reverse the conflicting movement before saving this interest correction.';

function parseMoney(value) {
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

function formatMoney(value, currency = 'INR') {
  if (value == null || Number.isNaN(value)) return '—';
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${Number(value).toFixed(2)} ${currency}`;
  }
}

/**
 * Shared actual interest credit form for FD list row and detail schedule (#42).
 * Forecast/suggested amounts are display-only until Save posts via the API.
 */
export default function FixedDepositInterestPaymentForm({
  form,
  onChange,
  onSubmit,
  onCancel,
  submitting = false,
  error = '',
  futureImpact = null,
  currency = 'INR',
  bankAccountName = '',
  title = 'Record interest payment',
  submitLabel = 'Save',
  /** Optional schedule forecast: { expected_payout_date, expected_gross_interest } */
  suggested = null,
  showApplyTaxHelper = true,
  showUnscheduledHint = true,
}) {
  const gross = parseMoney(form.gross_interest);
  const tax = parseMoney(form.tax_withheld || '0');
  const net = gross != null && tax != null ? gross - tax : null;
  const expectedGross =
    suggested?.expected_gross_interest != null
      ? Number(suggested.expected_gross_interest)
      : null;

  const variance = useMemo(() => {
    if (expectedGross == null || !Number.isFinite(expectedGross) || gross == null) {
      return null;
    }
    // Compare on the same basis: expected is labelled as gross when no expected net.
    const delta = gross - expectedGross;
    if (Math.abs(delta) < 0.005) {
      return { kind: 'match', delta: 0, label: 'Matches expected gross' };
    }
    return {
      kind: 'diff',
      delta,
      label: `Actual gross differs from expected gross by ${formatMoney(delta, currency)}`,
    };
  }, [currency, expectedGross, gross]);

  const applyTenPercentTax = () => {
    if (gross == null || gross <= 0) return;
    onChange({ ...form, tax_withheld: (gross * 0.1).toFixed(2) });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(e);
  };

  return (
    <form className="fd-interest-payment-form" onSubmit={handleSubmit} noValidate>
      <h3 className="fd-interest-payment-form__title">{title}</h3>
      {suggested ? (
        <p className="fd-interest-payment-form__forecast" data-testid="fd-interest-forecast">
          Forecast (gross estimate)
          {suggested.expected_payout_date ? ` · ${suggested.expected_payout_date}` : ''}
          {expectedGross != null ? ` · ${formatMoney(expectedGross, currency)}` : ''}
          . Confirm the actual bank credit below — forecasts create no ledger entries.
        </p>
      ) : showUnscheduledHint ? (
        <p className="fd-interest-payment-form__forecast" data-testid="fd-interest-unscheduled">
          Unscheduled payout — enter the actual credit from the bank statement.
        </p>
      ) : null}
      {futureImpact ? (
        <CashFutureImpactDisplay impact={futureImpact} helperText={BANK_FUTURE_IMPACT_HELPER} />
      ) : error ? (
        <WarningBanner severity="error" message={error} />
      ) : null}
      <div className="form-group">
        <label htmlFor="fd-interest-payment-date">Actual credited date</label>
        <input
          id="fd-interest-payment-date"
          type="date"
          value={form.payment_date}
          onChange={(e) => onChange({ ...form, payment_date: e.target.value })}
          required
        />
      </div>
      <div className="form-group">
        <label htmlFor="fd-interest-gross">Gross interest</label>
        <input
          id="fd-interest-gross"
          type="number"
          step="0.01"
          min="0.01"
          value={form.gross_interest}
          onChange={(e) => onChange({ ...form, gross_interest: e.target.value })}
          required
        />
      </div>
      <div className="form-group">
        <label htmlFor="fd-interest-tax">Tax withheld</label>
        <div className="fd-interest-payment-form__tax-row">
          <input
            id="fd-interest-tax"
            type="number"
            step="0.01"
            min="0"
            value={form.tax_withheld}
            onChange={(e) => onChange({ ...form, tax_withheld: e.target.value })}
          />
          {showApplyTaxHelper ? (
            <Button type="button" variant="secondary" size="sm" onClick={applyTenPercentTax}>
              Apply 10% tax
            </Button>
          ) : null}
        </div>
      </div>
      <div className="form-group">
        <label>Net bank credit</label>
        <div className="fd-interest-payment-form__net" data-testid="fd-interest-net">
          {net != null ? formatMoney(net, currency) : '—'}
        </div>
      </div>
      {variance ? (
        <p
          className={
            variance.kind === 'match'
              ? 'fd-interest-payment-form__variance fd-interest-payment-form__variance--ok'
              : 'fd-interest-payment-form__variance'
          }
          data-testid="fd-interest-variance"
        >
          {variance.label}
        </p>
      ) : null}
      <div className="form-group">
        <label htmlFor="fd-interest-comment">Note</label>
        <textarea
          id="fd-interest-comment"
          rows={2}
          value={form.comment}
          onChange={(e) => onChange({ ...form, comment: e.target.value })}
        />
      </div>
      {bankAccountName ? (
        <p className="fd-interest-payment-form__bank-hint">
          Credited to {bankAccountName} (FD funding bank account).
        </p>
      ) : null}
      <div className="fd-interest-payment-form__actions">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </Button>
      </div>
    </form>
  );
}

export function newInterestClientRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `fd-int-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
