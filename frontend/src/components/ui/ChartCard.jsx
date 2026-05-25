export default function ChartCard({
  title,
  subtitle,
  toolbar,
  children,
  footer,
  className = '',
  compact = false,
}) {
  const classes = [
    'ui-chart-card',
    compact ? 'ui-chart-card--compact' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const showHeader = title || subtitle || toolbar;

  return (
    <section className={classes}>
      {showHeader ? (
        <div className="ui-chart-card__header">
          <div className="ui-chart-card__heading">
            {title ? <h3 className="ui-chart-card__title">{title}</h3> : null}
            {subtitle ? <p className="ui-chart-card__subtitle">{subtitle}</p> : null}
          </div>
          {toolbar ? <div className="ui-chart-card__toolbar">{toolbar}</div> : null}
        </div>
      ) : null}
      <div className="ui-chart-card__body">{children}</div>
      {footer ? <div className="ui-chart-card__footer">{footer}</div> : null}
    </section>
  );
}
