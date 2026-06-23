export default function ChartCard({
  title,
  subtitle,
  toolbar,
  status,
  legend,
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

  const showHeader = title || subtitle || toolbar || status;

  return (
    <section className={classes}>
      {showHeader ? (
        <div className="ui-chart-card__header">
          <div className="ui-chart-card__heading">
            {title ? <h3 className="ui-chart-card__title">{title}</h3> : null}
            {subtitle ? <p className="ui-chart-card__subtitle">{subtitle}</p> : null}
          </div>
          {toolbar || status ? (
            <div className="ui-chart-card__toolbar">
              {status ? <div className="ui-chart-card__status">{status}</div> : null}
              {toolbar}
            </div>
          ) : null}
        </div>
      ) : null}
      {legend ? <div className="ui-chart-card__legend">{legend}</div> : null}
      <div className="ui-chart-card__body">{children}</div>
      {footer ? <div className="ui-chart-card__footer">{footer}</div> : null}
    </section>
  );
}
