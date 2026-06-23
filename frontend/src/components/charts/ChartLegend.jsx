export default function ChartLegend({ items = [], className = '', ariaLabel = 'Chart legend' }) {
  if (!items.length) {
    return null;
  }

  const classes = ['ui-chart-legend', className].filter(Boolean).join(' ');

  return (
    <ul className={classes} aria-label={ariaLabel}>
      {items.map((item) => (
        <li
          key={item.id}
          className={[
            'ui-chart-legend__item',
            item.role ? `ui-chart-legend__item--${item.role}` : '',
          ]
            .filter(Boolean)
            .join(' ')}
        >
          <span
            className="ui-chart-legend__swatch"
            style={{ backgroundColor: item.color }}
            aria-hidden="true"
          />
          <span className="ui-chart-legend__label">{item.label}</span>
        </li>
      ))}
    </ul>
  );
}
