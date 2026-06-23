/** Recharts presentation tokens — read from CSS variables for theme support. */

export const CHART_FONT_FAMILY = 'Inter, system-ui, sans-serif';

const FALLBACK = {
  grid: '#2a3544',
  axis: '#8b9cb3',
  surface: '#1a2332',
  border: '#2a3544',
  text: '#e8edf4',
  gain: '#22c55e',
  loss: '#ef4444',
  accent: '#3b82f6',
  charts: ['#3b82f6', '#22c55e', '#14b8a6', '#8b5cf6', '#f59e0b', '#64748b'],
};

function readCssVar(name, fallback) {
  if (typeof document === 'undefined') {
    return fallback;
  }
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export function getChartTooltipStyle() {
  return {
    backgroundColor: readCssVar('--bg-surface-raised', FALLBACK.surface),
    border: `1px solid ${readCssVar('--border-subtle', FALLBACK.border)}`,
    borderRadius: '6px',
    color: readCssVar('--text-primary', FALLBACK.text),
    fontSize: '0.75rem',
    fontFamily: CHART_FONT_FAMILY,
    boxShadow: readCssVar('--shadow-card', '0 1px 3px rgba(0, 0, 0, 0.4)'),
    padding: 0,
  };
}

export function getChartLegendStyle() {
  return {
    fontFamily: CHART_FONT_FAMILY,
    fontSize: 12,
    color: readCssVar('--text-secondary', FALLBACK.axis),
  };
}

export function getChartGridProps() {
  return {
    strokeDasharray: '4 8',
    stroke: readCssVar('--border-subtle', FALLBACK.grid),
  };
}

export function getChartAxisTick() {
  const stroke = readCssVar('--text-secondary', FALLBACK.axis);
  return {
    fontFamily: CHART_FONT_FAMILY,
    fill: stroke,
    fontSize: 12,
  };
}

export function getChartAxisStroke() {
  return readCssVar('--text-secondary', FALLBACK.axis);
}

export function getSeriesColor(index) {
  const token = `--chart-${(index % 6) + 1}`;
  return readCssVar(token, FALLBACK.charts[index % FALLBACK.charts.length]);
}

export function getBenchmarkLineColors() {
  return [getSeriesColor(0), getSeriesColor(5)];
}

export function getChartGainColor() {
  return readCssVar('--gain', FALLBACK.gain);
}

export function getChartLossColor() {
  return readCssVar('--loss', FALLBACK.loss);
}

export function getChartBarInvestedColor() {
  return readCssVar('--accent', FALLBACK.accent);
}

export function getChartCrosshairStroke() {
  return readCssVar('--border-strong', FALLBACK.border);
}

export function getPortfolioSeriesColor() {
  return getSeriesColor(0);
}

export function getBenchmarkSeriesColor() {
  return getBenchmarkLineColors()[1] ?? getSeriesColor(5);
}

export function getComparisonBarFill(currentValue, investedValue) {
  return Number(currentValue) >= Number(investedValue)
    ? getChartGainColor()
    : getChartLossColor();
}

/** @deprecated Use getChartTooltipStyle() */
export const CHART_TOOLTIP_STYLE = getChartTooltipStyle();

/** @deprecated Use getChartLegendStyle() */
export const CHART_LEGEND_STYLE = getChartLegendStyle();

/** @deprecated Use getChartGainColor() */
export const CHART_GAIN = FALLBACK.gain;

/** @deprecated Use getChartLossColor() */
export const CHART_LOSS = FALLBACK.loss;

/** @deprecated Use getChartBarInvestedColor() */
export const CHART_BAR_INVESTED = FALLBACK.accent;

/** @deprecated Use getChartGridProps() */
export const chartGridProps = getChartGridProps();

/** @deprecated Use getChartAxisStroke() */
export const chartAxisStroke = FALLBACK.axis;

/** @deprecated Use getChartAxisTick() */
export const chartAxisTick = getChartAxisTick();
