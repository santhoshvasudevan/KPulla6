import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { ChartCard } from '../ui';
import {
  chartGridProps,
  chartAxisStroke,
  chartAxisTick,
  CHART_TOOLTIP_STYLE,
  CHART_GAIN,
  CHART_LOSS,
} from '../charts/chartTheme';
import { formatMetricPercentFraction } from '../../utils/metricFormatters';
import { buildYearlyReturnChartData } from './metricSheetChartHelpers';
import './metricSheet.css';

function formatPercentAxis(fraction) {
  if (fraction == null || Number.isNaN(Number(fraction))) return '';
  return `${(Number(fraction) * 100).toFixed(1)}%`;
}

/**
 * Calendar-Year Return bar chart from backend `periodic_returns.yearly`.
 */
export default function MetricSheetYearlyReturnChart({ yearly = [], className = '' }) {
  const chartData = useMemo(() => buildYearlyReturnChartData(yearly), [yearly]);

  return (
    <ChartCard
      title="Calendar-Year Return"
      subtitle="Cash-flow adjusted return using daily TWROR."
      className={['metric-sheet-yearly-chart', className].filter(Boolean).join(' ')}
      compact
    >
      {!chartData.length ? (
        <p className="metric-sheet__empty-inline">
          No calendar-year return data available for this range.
        </p>
      ) : (
        <div className="metric-sheet-chart-panel">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
              <CartesianGrid {...chartGridProps} vertical={false} />
              <XAxis
                dataKey="period"
                stroke={chartAxisStroke}
                tick={chartAxisTick}
              />
              <YAxis
                stroke={chartAxisStroke}
                tick={chartAxisTick}
                tickFormatter={formatPercentAxis}
              />
              <Tooltip
                contentStyle={CHART_TOOLTIP_STYLE}
                formatter={(value) => [
                  formatMetricPercentFraction(value, { showSign: true }),
                  'Return',
                ]}
                labelFormatter={(label) => `Year ${label}`}
              />
              <Bar dataKey="return" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.period}
                    fill={
                      entry.return != null && Number(entry.return) < 0
                        ? CHART_LOSS
                        : CHART_GAIN
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </ChartCard>
  );
}
