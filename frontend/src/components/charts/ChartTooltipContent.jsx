/**
 * Compact chart tooltip body. Renders backend-provided / pre-formatted values only.
 */
export default function ChartTooltipContent({ label, items = [], delta, className = '' }) {
  const classes = ['ui-chart-tooltip__content', className].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      {label ? <p className="ui-chart-tooltip__label">{label}</p> : null}
      {items.length ? (
        <dl className="ui-chart-tooltip__rows">
          {items.map((item) => (
            <div
              key={item.key}
              className={[
                'ui-chart-tooltip__row',
                item.role ? `ui-chart-tooltip__row--${item.role}` : '',
                item.tone ? `ui-chart-tooltip__row--tone-${item.tone}` : '',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              <dt className="ui-chart-tooltip__term">
                {item.color ? (
                  <span
                    className="ui-chart-tooltip__swatch"
                    style={{ backgroundColor: item.color }}
                    aria-hidden="true"
                  />
                ) : null}
                <span>{item.label}</span>
              </dt>
              <dd className="ui-chart-tooltip__value">{item.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {delta?.value ? (
        <p className="ui-chart-tooltip__delta">
          {delta.label ? <span className="ui-chart-tooltip__delta-label">{delta.label}</span> : null}
          <span>{delta.value}</span>
        </p>
      ) : null}
    </div>
  );
}
