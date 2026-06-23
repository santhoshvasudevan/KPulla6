import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  getSeriesColor,
  getChartGridProps,
  getChartAxisStroke,
  getChartAxisTick,
  getChartTooltipStyle,
  getChartLegendStyle,
  ChartEmptyState,
  getChartCrosshairCursorProps,
  getChartActiveDotProps,
  getChartMinTickGap,
} from '../charts';
import { formatMetricPercentFraction } from '../../utils/metricFormatters';

/** Map backend normalized_series to Recharts rows (fractions unchanged). */
export function mergeNormalizedCompareSeries(normalizedSeries) {
  if (!Array.isArray(normalizedSeries) || normalizedSeries.length === 0) {
    return { chartData: [], subjectIds: [] };
  }
  const subjectIds = Object.keys(normalizedSeries[0]?.values || {});
  const chartData = normalizedSeries.map((pt) => {
    const row = { date: pt.date };
    for (const sid of subjectIds) {
      row[sid] = pt.values?.[sid];
    }
    return row;
  });
  return { chartData, subjectIds };
}

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

function formatAxisDayMonth(d) {
  try {
    const dt = new Date(`${d}T00:00:00Z`);
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(dt);
  } catch {
    return d;
  }
}

function formatPercentAxis(fraction) {
  if (fraction == null || Number.isNaN(Number(fraction))) return '';
  return `${(Number(fraction) * 100).toFixed(2)}%`;
}

export default function CompareNormalizedChart({
  normalizedSeries,
  subjects = [],
  shortRange = false,
  className = '',
  hideLegend = false,
}) {
  const { chartData, subjectIds } = useMemo(
    () => mergeNormalizedCompareSeries(normalizedSeries),
    [normalizedSeries]
  );

  const lines = useMemo(() => {
    const labelById = new Map(
      (subjects || []).map((s) => [s.id, s.name || s.asset_symbol || s.id])
    );
    return subjectIds.map((sid, index) => ({
      dataKey: sid,
      name: labelById.get(sid) || sid,
      stroke: getSeriesColor(index),
    }));
  }, [subjectIds, subjects]);

  const axisDateFormatter = shortRange ? formatAxisDayMonth : formatAxisMonthYear;

  if (!chartData.length) {
    return (
      <ChartEmptyState
        title="No comparison chart data"
        description="The backend returned no normalized cumulative return series for this selection."
      />
    );
  }

  return (
    <div className={['compare-normalized-chart', className].filter(Boolean).join(' ')}>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData}>
          <CartesianGrid {...getChartGridProps()} />
          <XAxis
            dataKey="date"
            stroke={getChartAxisStroke()}
            tick={getChartAxisTick()}
            tickFormatter={axisDateFormatter}
            interval="preserveStartEnd"
            minTickGap={getChartMinTickGap('analysis', shortRange)}
          />
          <YAxis
            stroke={getChartAxisStroke()}
            tick={getChartAxisTick()}
            tickFormatter={formatPercentAxis}
          />
          <Tooltip
            contentStyle={getChartTooltipStyle()}
            cursor={getChartCrosshairCursorProps('analysis')}
            formatter={(value) => formatMetricPercentFraction(value, { showSign: true })}
            labelFormatter={(l) => axisDateFormatter(l)}
          />
          {lines.length > 1 && !hideLegend ? (
            <Legend wrapperStyle={getChartLegendStyle()} />
          ) : null}
          {lines.map((line) => (
            <Line
              key={line.dataKey}
              type="monotone"
              dataKey={line.dataKey}
              name={line.name}
              stroke={line.stroke}
              dot={false}
              activeDot={getChartActiveDotProps('secondary')}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
