import { formatCurrency } from '../../utils/formatters';

export default function CurrencyValue({
  value,
  currency = 'EUR',
  tone = 'neutral',
  fallback = '—',
  showSign = false,
  className = '',
}) {
  const classes = ['ui-currency-value', `ui-currency-value--${tone}`, className]
    .filter(Boolean)
    .join(' ');

  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return <span className={classes}>{fallback}</span>;
  }

  const num = Number(value);
  const sign = num < 0 ? '−' : showSign && num > 0 ? '+' : '';

  return (
    <span className={classes}>
      {sign}
      {formatCurrency(Math.abs(num), currency)}
    </span>
  );
}
