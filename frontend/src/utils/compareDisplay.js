import { getSeriesColor } from '../components/charts/chartTheme';
import { mergeNormalizedCompareSeries } from '../components/metricSheet/CompareNormalizedChart';

export function compareOptionLabel(assetOptions, symbol) {
  if (!symbol) return '';
  return assetOptions.find((o) => o.symbol === symbol)?.label || symbol;
}

export function compareBenchmarkLabel(benchmarkOptions, symbol) {
  if (!symbol) return '';
  const row = benchmarkOptions.find((b) => b.symbol === symbol);
  return row?.name || row?.display_name || symbol;
}

/** Display-only legend items from backend subjects and normalized series order. */
export function compareChartLegendItems(subjects = [], normalizedSeries = []) {
  const { subjectIds } = mergeNormalizedCompareSeries(normalizedSeries);
  const labelById = new Map(
    (subjects || []).map((s) => [s.id, s.name || s.asset_symbol || s.id])
  );
  return subjectIds.map((sid, index) => ({
    id: sid,
    label: labelById.get(sid) || sid,
    color: getSeriesColor(index),
    role: 'subject',
  }));
}

/** Display-only KPI values from backend subject metrics — no calculations. */
export function compareSubjectSummaryKpis(subjects = []) {
  return (subjects || []).map((s, index) => ({
    id: s.id,
    label: s.name || s.asset_symbol || s.id,
    cumulativeReturn: s.metrics?.return?.cumulative_return ?? null,
    volatility: s.metrics?.risk?.volatility_annualized ?? null,
    maxDrawdown: s.metrics?.drawdown?.max_drawdown ?? null,
    colorIndex: index,
  }));
}
