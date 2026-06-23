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
import {
  ChartFrame,
  getChartGridProps,
  getChartAxisStroke,
  getChartAxisTick,
  getChartTooltipStyle,
  getChartGainColor,
  getChartLossColor,
  getChartCrosshairCursorProps,
} from '../charts';
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
    <ChartFrame
      title="Calendar-Year Return"
      subtitle="Cash-flow adjusted return using daily TWROR."
      className={['metric-sheet-yearly-chart', className].filter(Boolean).join(' ')}
      panelClassName="metric-sheet-chart-panel"
      compact
      density="analysis"
      empty={!chartData.length}
      emptyVariant="inline"
      emptyDescription="No calendar-year return data available for this range."
    >
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid {...getChartGridProps()} vertical={false} />
          <XAxis dataKey="period" stroke={getChartAxisStroke()} tick={getChartAxisTick()} />
          <YAxis
            stroke={getChartAxisStroke()}
            tick={getChartAxisTick()}
            tickFormatter={formatPercentAxis}
          />
          <Tooltip
            contentStyle={getChartTooltipStyle()}
            cursor={getChartCrosshairCursorProps('analysis')}
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
                    ? getChartLossColor()
                    : getChartGainColor()
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
