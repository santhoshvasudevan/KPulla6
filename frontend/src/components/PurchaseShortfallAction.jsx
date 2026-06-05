import { Button } from './ui';

/**
 * User-confirmed add missing same-currency cash and retry BUY (Cash-4C).
 */
export default function PurchaseShortfallAction({
  shortfall,
  sourceOfFunds,
  note,
  onSourceOfFundsChange,
  onNoteChange,
  onConfirm,
  loading = false,
  disabled = false,
  idPrefix = 'purchase-shortfall',
}) {
  if (!shortfall?.currency) return null;

  return (
    <section
      className="modal-purchase-shortfall-action"
      aria-labelledby={`${idPrefix}-title`}
    >
      <h4 id={`${idPrefix}-title`} className="modal-purchase-shortfall-action__title">
        Recommended action
      </h4>
      <p className="modal-purchase-shortfall-action__text">
        Add the missing {shortfall.currency} cash deposit and continue with this purchase.
      </p>
      <div className="form-group">
        <label htmlFor={`${idPrefix}-source`}>Source of funds</label>
        <input
          id={`${idPrefix}-source`}
          type="text"
          value={sourceOfFunds}
          onChange={(e) => onSourceOfFundsChange(e.target.value)}
          disabled={loading || disabled}
          placeholder="Optional"
        />
      </div>
      <div className="form-group">
        <label htmlFor={`${idPrefix}-note`}>Note</label>
        <textarea
          id={`${idPrefix}-note`}
          rows={2}
          value={note}
          onChange={(e) => onNoteChange(e.target.value)}
          disabled={loading || disabled}
          placeholder="Optional"
        />
      </div>
      {loading ? (
        <p className="modal-purchase-shortfall-action__status" role="status">
          Adding cash and recording purchase…
        </p>
      ) : null}
      <Button
        type="button"
        variant="primary"
        onClick={onConfirm}
        disabled={loading || disabled}
      >
        Add missing cash and continue
      </Button>
    </section>
  );
}
