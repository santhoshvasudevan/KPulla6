import { CurrencyValue } from './ui';

/**
 * Displays backend shortfall fields (required / available / shortfall / currency).
 * React does not compute these values.
 *
 * @param {'purchase' | undefined} variant — `purchase` adds same-currency BUY guidance (not for withdrawals).
 */
export function purchaseShortfallGuidance(currency) {
  return `Purchases require cash in the transaction currency. Add or edit ${currency} cash in this portfolio, then retry.`;
}

export default function CashShortfallDisplay({
  shortfall,
  variant,
  className = 'modal-cash-shortfall',
}) {
  if (!shortfall) return null;
  return (
    <div className={className}>
      <p>
        Required:{' '}
        <CurrencyValue value={shortfall.required} currency={shortfall.currency} />
      </p>
      <p>
        Available:{' '}
        <CurrencyValue value={shortfall.available} currency={shortfall.currency} />
      </p>
      <p>
        Shortfall:{' '}
        <CurrencyValue value={shortfall.shortfall} currency={shortfall.currency} tone="loss" />
      </p>
      {variant === 'purchase' && shortfall.currency ? (
        <p className="modal-cash-shortfall__guidance">
          {purchaseShortfallGuidance(shortfall.currency)}
        </p>
      ) : null}
    </div>
  );
}
