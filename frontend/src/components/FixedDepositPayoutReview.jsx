import { useState } from 'react';
import { resolveFixedDepositPendingPayoutDiscrepancy } from '../api';
import { Button, CurrencyValue, StatusBadge, WarningBanner } from './ui';
import './FixedDepositPayoutReview.css';

export function payoutDiscrepancyBadgeProps(discrepancyStatus) {
  if (discrepancyStatus === 'OPEN') return { status: 'warning', label: 'Discrepancy open' };
  if (discrepancyStatus === 'RESOLVED') return { status: 'ok', label: 'Discrepancy resolved' };
  return null;
}

/** Backend `discrepancy_amount` is signed actual − estimated net; label only, no recomputation. */
export function PayoutDifferenceValue({ amount, currency }) {
  if (amount == null) return '—';
  const kind = amount < 0 ? 'shortfall' : 'excess';
  return (
    <span className={`fd-payout-review__difference fd-payout-review__difference--${kind}`}>
      <CurrencyValue value={Math.abs(amount)} currency={currency} /> {kind}
    </span>
  );
}

/**
 * Final maturity payout review block (#46): estimate vs actual net as returned by the API.
 * Resolving changes review metadata only — amounts and the bank credit stay as confirmed.
 */
export function FixedDepositPayoutReviewSummary({ payout, onResolve = null }) {
  if (!payout) return null;
  const { currency } = payout;
  const badge = payoutDiscrepancyBadgeProps(payout.discrepancy_status);
  const confirmed = payout.status === 'CONFIRMED';
  return (
    <div className="fd-payout-review" data-testid="fd-payout-review">
      {payout.discrepancy_status === 'OPEN' ? (
        <WarningBanner
          severity="warning"
          message="Actual payout differs from the estimate. The confirmed amount is already posted; review and resolve with a note."
        />
      ) : null}
      <dl className="fd-payout-review__grid">
        <div className="fd-payout-review__item">
          <dt>Estimated net</dt>
          <dd>
            {payout.suggested_net_interest != null ? (
              <CurrencyValue value={payout.suggested_net_interest} currency={currency} />
            ) : (
              'No estimate'
            )}
          </dd>
        </div>
        <div className="fd-payout-review__item">
          <dt>Actual net posted</dt>
          <dd>
            {confirmed && payout.net_interest != null ? (
              <>
                <CurrencyValue value={payout.net_interest} currency={currency} />
                {payout.payment_date ? (
                  <span className="fd-payout-review__note"> on {payout.payment_date}</span>
                ) : null}
              </>
            ) : (
              'Awaiting bank credit'
            )}
          </dd>
        </div>
        <div className="fd-payout-review__item">
          <dt>Difference</dt>
          <dd>
            <PayoutDifferenceValue amount={payout.discrepancy_amount} currency={currency} />
          </dd>
        </div>
        <div className="fd-payout-review__item">
          <dt>Review</dt>
          <dd>
            {badge ? (
              <StatusBadge {...badge} />
            ) : (
              <span className="fd-payout-review__note">
                {confirmed ? 'No discrepancy' : 'Pending confirmation'}
              </span>
            )}
          </dd>
        </div>
      </dl>
      {payout.discrepancy_status === 'RESOLVED' && payout.resolution_comment ? (
        <p className="fd-payout-review__resolution">
          Resolved{payout.resolved_at ? ` ${payout.resolved_at.slice(0, 10)}` : ''}:{' '}
          {payout.resolution_comment}
        </p>
      ) : null}
      {payout.discrepancy_status === 'OPEN' && onResolve ? (
        <div className="fd-payout-review__actions">
          <Button type="button" variant="primary" onClick={() => onResolve(payout)}>
            Resolve discrepancy
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function FixedDepositPayoutResolveModal({
  payout,
  termLabel = '',
  onClose,
  onResolved,
  backdropClassName = 'fd-modal-backdrop',
  modalClassName = 'fd-modal',
}) {
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!payout) return null;

  const handleSubmit = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    const note = comment.trim();
    if (!note) {
      setError('A comment is required to resolve the discrepancy.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const result = await resolveFixedDepositPendingPayoutDiscrepancy(payout.id, note);
      await onResolved?.(result);
    } catch (err) {
      setError(err.message || 'Failed to resolve discrepancy.');
      setSubmitting(false);
    }
  };

  return (
    <div className={backdropClassName} role="presentation" onClick={onClose}>
      <div
        className={modalClassName}
        role="dialog"
        aria-modal="true"
        aria-labelledby="fd-payout-resolve-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="fd-payout-resolve-title">Resolve payout discrepancy</h2>
        {termLabel ? <p className="settings-hint">{termLabel}</p> : null}
        <FixedDepositPayoutReviewSummary payout={payout} />
        <p className="settings-hint">
          Resolving records your review note only. The posted bank credit, confirmed amounts,
          and interest report totals do not change.
        </p>
        {error ? <WarningBanner severity="error" message={error} /> : null}
        <form onSubmit={handleSubmit} className="fd-form">
          <div className="form-group">
            <label htmlFor="fd-payout-resolve-comment">Resolution comment (required)</label>
            <textarea
              id="fd-payout-resolve-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              maxLength={1000}
            />
          </div>
          <div className="fd-form__actions">
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? 'Resolving…' : 'Mark resolved'}
            </Button>
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
