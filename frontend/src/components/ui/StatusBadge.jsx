const STATUS_LABELS = {
  ok: 'OK',
  success: 'Success',
  gain: 'Gain',
  closed: 'Closed',
  oversold: 'Oversold',
  price_missing: 'Price missing',
  fx_unavailable: 'FX unavailable',
  warning: 'Warning',
  info: 'Info',
  danger: 'Danger',
  loss: 'Loss',
  error: 'Error',
  neutral: 'Neutral',
  verified: 'NAV verified',
  nav_warning: 'NAV check',
};

export default function StatusBadge({ status = 'neutral', label, className = '', ariaLabel }) {
  const text = label ?? STATUS_LABELS[status] ?? status;
  const classes = ['ui-status-badge', `ui-status-badge--${status}`, className]
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classes} role="status" aria-label={ariaLabel ?? text}>
      {text}
    </span>
  );
}
