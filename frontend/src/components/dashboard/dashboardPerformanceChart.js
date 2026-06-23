import {
  getSeriesColorForRole,
  CHART_SERIES_ROLES,
} from '../charts/chartSeries';

/** Preserve backend null/missing; never coerce to zero for chart display. */
export function normalizePerformancePointValue(raw) {
  if (raw == null || raw === '') return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function mergeComparisonSeries(payload) {
  const byDate = new Map();
  for (const s of payload.series || []) {
    const key = s.name;
    for (const pt of s.data || []) {
      if (!byDate.has(pt.date)) byDate.set(pt.date, { date: pt.date });
      byDate.get(pt.date)[key] = normalizePerformancePointValue(pt.value);
    }
  }
  return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
}

function isReturnMetric(metric) {
  return metric === 'cumulative_return' || metric === 'twror';
}

function isComparisonPerformancePayload(performanceData, metric) {
  return (
    isReturnMetric(metric) &&
    typeof performanceData === 'object' &&
    performanceData != null &&
    !Array.isArray(performanceData) &&
    Array.isArray(performanceData.series)
  );
}

function isPointsWithWarningsPayload(performanceData) {
  return (
    typeof performanceData === 'object' &&
    performanceData != null &&
    !Array.isArray(performanceData) &&
    Array.isArray(performanceData.points)
  );
}

function resolvePerformancePoints(performanceData, metric) {
  if (!performanceData) return [];
  if (Array.isArray(performanceData)) return performanceData;
  if (metric === 'value' && isPointsWithWarningsPayload(performanceData)) {
    return performanceData.points;
  }
  if (isReturnMetric(metric) && isComparisonPerformancePayload(performanceData, metric)) {
    return null;
  }
  if (isPointsWithWarningsPayload(performanceData)) {
    return performanceData.points;
  }
  return [];
}

/**
 * Map fetchPortfolioPerformance payload to Recharts data without finance calculations.
 */
export function buildDashboardPerformanceChartConfig(
  performanceData,
  { metric, chartMetricLabel, displayCurrency }
) {
  if (!performanceData) {
    return { chartData: [], lines: [], comparisonWarnings: [] };
  }

  if (isComparisonPerformancePayload(performanceData, metric)) {
    const chartData = mergeComparisonSeries(performanceData);
    const lines = (performanceData.series || []).map((s) => {
      const role =
        s.type === 'benchmark' ? CHART_SERIES_ROLES.benchmark : CHART_SERIES_ROLES.portfolio;
      return {
        dataKey: s.name,
        name: s.name,
        stroke: getSeriesColorForRole(role),
        role,
      };
    });
    return {
      chartData,
      lines,
      comparisonWarnings: performanceData.warnings || [],
    };
  }

  const arr = resolvePerformancePoints(performanceData, metric);
  const chartData = arr.map((p) => ({
    date: p.date,
    value: normalizePerformancePointValue(p.value),
    currency: p.currency || displayCurrency,
  }));

  const comparisonWarnings = isPointsWithWarningsPayload(performanceData)
    ? performanceData.warnings || []
    : [];

  return {
    chartData,
    lines: [
      {
        dataKey: 'value',
        name: chartMetricLabel,
        stroke: getSeriesColorForRole(CHART_SERIES_ROLES.portfolio),
        role: CHART_SERIES_ROLES.portfolio,
      },
    ],
    comparisonWarnings,
  };
}

/** Latest chronologically valid point for the selected series key (readout/tooltip context). */
export function findLatestValidChartReading(chartData, dataKey = 'value') {
  if (!Array.isArray(chartData) || !chartData.length) return null;
  for (let i = chartData.length - 1; i >= 0; i -= 1) {
    const point = chartData[i];
    const value = normalizePerformancePointValue(point?.[dataKey]);
    if (value != null) {
      return { date: point.date, value };
    }
  }
  return null;
}
