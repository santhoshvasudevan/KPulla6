import { formatPercent } from '../../utils/formatters';

export default function PercentValue({
  value,
  tone = 'neutral',
  fallback = 'N/A',
  showSign = false,
  className = '',
}) {
  const classes = ['ui-percent-value', `ui-percent-value--${tone}`, className]
    .filter(Boolean)
    .join(' ');

  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return <span className={classes}>{fallback}</span>;
  }

  const num = Number(value);
  const formatted = formatPercent(Math.abs(num));
  let prefix = '';
  if (showSign) {
    prefix = num > 0 ? '+' : num < 0 ? '−' : '';
  }

  return (
    <span className={classes}>
      {prefix}
      {num < 0 ? `−${formatted}` : formatted}
    </span>
  );
}
