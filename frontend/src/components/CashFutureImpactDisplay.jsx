import { CurrencyValue } from './ui';
import { cashEntryTypeLabel } from '../utils/cashDisplay';

export const CASH_FUTURE_IMPACT_HELPER =
  'Please add another cash deposit, edit later transactions, or delete affected transactions manually before changing this cash entry.';

export const TRANSACTION_FUTURE_IMPACT_INTRO =
  'This transaction cannot be deleted or changed because its linked cash settlement funded later transactions.';

export const TRANSACTION_FUTURE_IMPACT_HELPER =
  'Add another cash deposit, edit later transactions, or delete affected transactions manually before changing this transaction.';

/**
 * Backend future-impact rejection (edit/delete manual cash entry or asset transaction).
 */
export default function CashFutureImpactDisplay({
  impact,
  className = 'cash-future-impact',
  intro,
  helperText = CASH_FUTURE_IMPACT_HELPER,
}) {
  if (!impact) return null;
  const entries = Array.isArray(impact.affected_entries) ? impact.affected_entries : [];

  return (
    <div className={className}>
      {intro ? <p className="cash-future-impact__intro">{intro}</p> : null}
      {impact.detail ? <p className="cash-future-impact__detail">{impact.detail}</p> : null}
      {impact.currency && impact.earliest_negative_date ? (
        <p>
          Earliest negative balance on{' '}
          <strong>{impact.earliest_negative_date}</strong> ({impact.currency}).
        </p>
      ) : null}
      {impact.lowest_balance != null && impact.currency ? (
        <p>
          Lowest balance:{' '}
          <CurrencyValue value={impact.lowest_balance} currency={impact.currency} tone="loss" />
        </p>
      ) : null}
      {entries.length > 0 ? (
        <>
          <p className="cash-future-impact__list-title">Affected ledger entries</p>
          <ul className="cash-future-impact__list">
            {entries.map((row) => (
              <li key={row.id}>
                {row.date} — {cashEntryTypeLabel(row.entry_type)}
                {row.asset_symbol ? ` (${row.asset_symbol})` : ''}:{' '}
                <CurrencyValue value={row.amount} currency={impact.currency} tone="loss" />
                {row.linked_transaction_id != null
                  ? ` · transaction #${row.linked_transaction_id}`
                  : ''}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <p className="cash-future-impact__helper">{helperText}</p>
    </div>
  );
}
