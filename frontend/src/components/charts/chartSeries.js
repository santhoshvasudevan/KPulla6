import {
  getSeriesColor,
  getChartGainColor,
  getChartLossColor,
  getBenchmarkLineColors,
} from './chartTheme';

export const CHART_SERIES_ROLES = {
  portfolio: 'portfolio',
  benchmark: 'benchmark',
  secondary: 'secondary',
  muted: 'muted',
  gain: 'gain',
  loss: 'loss',
};

/** Resolve a stable series color from role or index without computing values. */
export function getSeriesColorForRole(role = 'secondary', index = 0) {
  switch (role) {
    case CHART_SERIES_ROLES.portfolio:
      return getSeriesColor(0);
    case CHART_SERIES_ROLES.benchmark:
      return getBenchmarkLineColors()[1] ?? getSeriesColor(5);
    case CHART_SERIES_ROLES.secondary:
      return getSeriesColor(2);
    case CHART_SERIES_ROLES.muted:
      return getSeriesColor(5);
    case CHART_SERIES_ROLES.gain:
      return getChartGainColor();
    case CHART_SERIES_ROLES.loss:
      return getChartLossColor();
    default:
      return getSeriesColor(index);
  }
}

/** Recharts line/area stroke props by semantic role. */
export function getSeriesStrokeProps(role = 'secondary') {
  if (role === CHART_SERIES_ROLES.benchmark) {
    return { strokeWidth: 1.5, strokeDasharray: '6 6', strokeOpacity: 0.62 };
  }
  if (role === CHART_SERIES_ROLES.muted) {
    return { strokeWidth: 1.5, strokeDasharray: '4 4', strokeOpacity: 0.75 };
  }
  if (role === CHART_SERIES_ROLES.portfolio) {
    return { strokeWidth: 2.5 };
  }
  return { strokeWidth: 2 };
}

/** Build legend items from pre-resolved line metadata. */
export function buildLegendItems(lines = []) {
  return lines.map((line, index) => ({
    id: line.dataKey ?? line.id ?? `series-${index}`,
    label: line.name ?? line.label ?? line.dataKey ?? `Series ${index + 1}`,
    color: line.stroke ?? line.color ?? getSeriesColorForRole(line.role, index),
    role: line.role ?? CHART_SERIES_ROLES.secondary,
  }));
}
