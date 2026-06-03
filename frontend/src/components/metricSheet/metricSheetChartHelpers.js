/** Display-only helpers: map backend Metric Sheet chart payloads for Recharts. */

/**
 * Organize backend `periodic_returns.yearly` rows for a bar chart (no return math).
 */
export function buildYearlyReturnChartData(yearly = []) {
  return [...yearly]
    .filter((row) => row?.period != null && row?.period !== '')
    .sort((a, b) => String(a.period).localeCompare(String(b.period)))
    .map((row) => ({
      period: String(row.period),
      return: row.return,
    }));
}

/**
 * Map backend `drawdown_series` to chart rows (fractions unchanged).
 */
export function buildDrawdownChartData(drawdownSeries = []) {
  return (drawdownSeries || [])
    .filter((pt) => pt?.date != null)
    .map((pt) => ({
      date: pt.date,
      drawdown: pt.drawdown,
    }));
}

const MIN_RANK_OPACITY = 0.06;
const MAX_RANK_OPACITY = 0.35;
const MAX_RANK = 10;

/** Opacity for worst-drawdown region shading (rank 1 = strongest). */
export function drawdownRankOpacity(rank) {
  const r = Number(rank);
  if (!Number.isFinite(r) || r < 1) return MIN_RANK_OPACITY;
  const clamped = Math.min(r, MAX_RANK);
  const step = (MAX_RANK_OPACITY - MIN_RANK_OPACITY) / (MAX_RANK - 1);
  return MAX_RANK_OPACITY - (clamped - 1) * step;
}

/**
 * Shade windows from backend worst drawdown episodes.
 * Unrecovered episodes extend through `seriesEndDate` (last visible series date).
 */
export function buildDrawdownShadeRegions(worstPeriods = [], seriesEndDate = null) {
  return (worstPeriods || [])
    .filter((ep) => ep?.start_date)
    .map((ep, index) => {
      const rank = ep.rank ?? index + 1;
      const end = ep.recovery_date || seriesEndDate || ep.trough_date;
      return {
        key: `${ep.start_date}-${ep.trough_date}-${rank}`,
        rank,
        start: ep.start_date,
        end,
        opacity: drawdownRankOpacity(rank),
      };
    });
}
