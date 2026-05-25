const STATUS_LABELS = {
  ok: 'OK',
  closed: 'Closed',
  oversold: 'Oversold',
  price_missing: 'Price missing',
  fx_unavailable: 'FX unavailable',
  warning: 'Warning',
  error: 'Error',
  neutral: 'Neutral',
};

export default function StatusBadge({ status = 'neutral', label, className = '' }) {
  const text = label ?? STATUS_LABELS[status] ?? status;
  const classes = ['ui-status-badge', `ui-status-badge--${status}`, className]
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classes} role="status">
      {text}
    </span>
  );
}
