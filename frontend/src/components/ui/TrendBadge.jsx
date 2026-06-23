const TREND_LABELS = {
  gain: 'Gain',
  success: 'Gain',
  loss: 'Loss',
  danger: 'Loss',
  warning: 'Warning',
  info: 'Info',
  neutral: 'Neutral',
};

export default function TrendBadge({ variant = 'neutral', label, value, className = '' }) {
  const semanticLabel = TREND_LABELS[variant] ?? variant;
  const text = label ?? value ?? semanticLabel;
  const classes = ['ui-trend-badge', `ui-trend-badge--${variant}`, className]
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classes} aria-label={`${semanticLabel}: ${text}`}>
      {text}
    </span>
  );
}
