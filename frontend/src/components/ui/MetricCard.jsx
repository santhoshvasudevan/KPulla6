export default function MetricCard({
  label,
  value,
  helperText,
  tone = 'neutral',
  size = 'default',
  icon,
  trend,
  className = '',
}) {
  const classes = [
    'ui-metric-card',
    tone !== 'neutral' ? `ui-metric-card--${tone}` : '',
    size === 'compact' ? 'ui-metric-card--compact' : '',
    size === 'hero' ? 'ui-metric-card--hero' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes}>
      <div className="ui-metric-card__header">
        {icon ? <span className="ui-metric-card__icon">{icon}</span> : null}
        {label ? <span className="ui-metric-card__label">{label}</span> : null}
      </div>
      {value != null && value !== '' ? (
        <div className="ui-metric-card__value">{value}</div>
      ) : null}
      {trend ? <div className="ui-metric-card__trend">{trend}</div> : null}
      {helperText ? <div className="ui-metric-card__helper">{helperText}</div> : null}
    </div>
  );
}
