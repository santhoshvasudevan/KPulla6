/** Recharts presentation tokens — mirrors Institutional Slate CSS variables. */

export const CHART_GRID_STROKE = '#2a3544';
export const CHART_AXIS_STROKE = '#8b9cb3';
export const CHART_FONT_FAMILY = 'Inter, system-ui, sans-serif';

export const CHART_TOOLTIP_STYLE = {
  backgroundColor: '#1a2332',
  border: '1px solid #2a3544',
  borderRadius: '6px',
  color: '#e8edf4',
  fontSize: '0.8125rem',
  fontFamily: CHART_FONT_FAMILY,
};

export const CHART_LEGEND_STYLE = {
  fontFamily: CHART_FONT_FAMILY,
  fontSize: 12,
  color: '#8b9cb3',
};

export const CHART_SERIES_PALETTE = [
  '#3b82f6',
  '#22c55e',
  '#14b8a6',
  '#8b5cf6',
  '#f59e0b',
  '#64748b',
];

export const CHART_GAIN = '#22c55e';
export const CHART_LOSS = '#ef4444';
export const CHART_BAR_INVESTED = '#3b82f6';

export function getSeriesColor(index) {
  return CHART_SERIES_PALETTE[index % CHART_SERIES_PALETTE.length];
}

export function getBenchmarkLineColors() {
  return [CHART_SERIES_PALETTE[0], CHART_SERIES_PALETTE[5]];
}

export function getComparisonBarFill(currentValue, investedValue) {
  return Number(currentValue) >= Number(investedValue) ? CHART_GAIN : CHART_LOSS;
}

export const chartGridProps = {
  strokeDasharray: '3 3',
  stroke: CHART_GRID_STROKE,
};

export const chartAxisStroke = CHART_AXIS_STROKE;

export const chartAxisTick = {
  fontFamily: CHART_FONT_FAMILY,
  fill: CHART_AXIS_STROKE,
  fontSize: 12,
};
