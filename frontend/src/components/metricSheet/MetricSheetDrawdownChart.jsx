import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
} from 'recharts';
import { ChartCard } from '../ui';
import {
  getChartGridProps,
  getChartAxisStroke,
  getChartAxisTick,
  getChartTooltipStyle,
  getChartLossColor,
} from '../charts/chartTheme';
import { formatMetricPercentFraction } from '../../utils/metricFormatters';
import {
  buildDrawdownChartData,
  buildDrawdownShadeRegions,
} from './metricSheetChartHelpers';
import './metricSheet.css';

function formatAxisMonthYear(d) {
  try {
    const dt = new Date(`${d}T00:00:00Z`);
    const mon = new Intl.DateTimeFormat('en-US', { month: 'short' }).format(dt);
    const yy = String(dt.getUTCFullYear() % 100).padStart(2, '0');
    return `${mon}-${yy}`;
  } catch {
    return d;
  }
}

function formatPercentAxis(fraction) {
  if (fraction == null || Number.isNaN(Number(fraction))) return '';
  return `${(Number(fraction) * 100).toFixed(1)}%`;
}

/**
 * Drawdown area chart from backend `drawdown_series` with worst-period shading.
 */
export default function MetricSheetDrawdownChart({
  drawdownSeries = [],
  drawdownPeriods,
  className = '',
}) {
  const chartData = useMemo(
    () => buildDrawdownChartData(drawdownSeries),
    [drawdownSeries]
  );

  const seriesEndDate = chartData.length ? chartData[chartData.length - 1].date : null;

  const shadeRegions = useMemo(
    () => buildDrawdownShadeRegions(drawdownPeriods?.worst ?? [], seriesEndDate),
    [drawdownPeriods, seriesEndDate]
  );

  return (
    <ChartCard
      title="Drawdown"
      className={['metric-sheet-drawdown-chart', className].filter(Boolean).join(' ')}
      compact
    >
      {!chartData.length ? (
        <p className="metric-sheet__empty-inline">
          No drawdown series data available for this range.
        </p>
      ) : (
        <div
          className="metric-sheet-chart-panel"
          data-drawdown-regions={shadeRegions.length ? 'true' : 'false'}
          data-drawdown-ranks={shadeRegions.map((region) => region.rank).join(',')}
        >
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
              <CartesianGrid {...getChartGridProps()} />
              {shadeRegions.map((region) => (
                <ReferenceArea
                  key={region.key}
                  x1={region.start}
                  x2={region.end}
                  fill={getChartLossColor()}
                  fillOpacity={region.opacity}
                  className={`metric-sheet-drawdown-chart__region metric-sheet-drawdown-chart__region--rank-${Math.min(region.rank, 10)}`}
                  ifOverflow="extendDomain"
                />
              ))}
              <XAxis
                dataKey="date"
                stroke={getChartAxisStroke()}
                tick={getChartAxisTick()}
                tickFormatter={formatAxisMonthYear}
                interval="preserveStartEnd"
                minTickGap={24}
              />
              <YAxis
                stroke={getChartAxisStroke()}
                tick={getChartAxisTick()}
                tickFormatter={formatPercentAxis}
                domain={['dataMin', 0]}
              />
              <Tooltip
                contentStyle={getChartTooltipStyle()}
                formatter={(value) => [
                  formatMetricPercentFraction(value, { showSign: true }),
                  'Drawdown',
                ]}
                labelFormatter={(label) => formatAxisMonthYear(label)}
              />
              <Area
                type="monotone"
                dataKey="drawdown"
                stroke={getChartLossColor()}
                fill={getChartLossColor()}
                fillOpacity={0.15}
                strokeWidth={2}
                isAnimationActive={false}
                connectNulls
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </ChartCard>
  );
}
