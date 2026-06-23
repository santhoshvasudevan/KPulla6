import { getChartTooltipStyle } from './chartTheme';
import ChartTooltipContent from './ChartTooltipContent';
import { formatChartTooltipValue } from './chartFormatters';
import { CHART_SERIES_ROLES } from './chartSeries';

function resolveItemRole(entry, benchmarkKeys = []) {
  const key = entry?.dataKey;
  if (benchmarkKeys.includes(key) || entry?.name === 'Benchmark') {
    return CHART_SERIES_ROLES.benchmark;
  }
  if (entry?.name === 'Portfolio' || key === 'portfolio' || key === 'Portfolio') {
    return CHART_SERIES_ROLES.portfolio;
  }
  return CHART_SERIES_ROLES.secondary;
}

/**
 * Recharts-compatible tooltip content. Formats provided payload values only.
 */
export default function ChartRechartsTooltip({
  active,
  payload,
  label,
  labelFormatter,
  valueKind = 'percent',
  currency,
  showSign = true,
  benchmarkKeys = [],
  delta,
  formatValue,
  className = '',
}) {
  if (!active || !payload?.length) {
    return null;
  }

  const formattedLabel = labelFormatter ? labelFormatter(label) : label;
  const items = payload
    .filter((entry) => entry?.value != null && entry.value !== '')
    .map((entry) => ({
      key: String(entry.dataKey ?? entry.name),
      label: entry.name ?? entry.dataKey,
      value: formatValue
        ? formatValue(entry.value, entry)
        : formatChartTooltipValue(entry.value, {
            kind: valueKind,
            currency,
            showSign,
          }),
      color: entry.color ?? entry.stroke,
      role: resolveItemRole(entry, benchmarkKeys),
    }));

  return (
    <div className={['ui-chart-tooltip', className].filter(Boolean).join(' ')} style={getChartTooltipStyle()}>
      <ChartTooltipContent label={formattedLabel} items={items} delta={delta} />
    </div>
  );
}
