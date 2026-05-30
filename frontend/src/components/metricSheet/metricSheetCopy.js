/** User-facing Metric Sheet copy (display only). */

export const METRIC_SHEET_XIRR_FULL_SCOPE_NOTE =
  'XIRR is full-scope; other Metric Sheet values follow the selected range.';

/**
 * Compare page: requested range vs backend-aligned common window.
 * @param {string} timeRange — selected control value (fallback if API omits range.code)
 * @param {object|null} compareData — compare API payload
 */
export function formatCompareRangeContext(timeRange, compareData) {
  if (!compareData) return null;

  const requested = compareData.range?.code || timeRange;
  const parts = [`Requested range: ${requested}`];

  if (compareData.common_start_date && compareData.common_end_date) {
    parts.push(
      `Compared over common dates: ${compareData.common_start_date} to ${compareData.common_end_date}`
    );
  }

  if (compareData.common_point_count != null) {
    parts.push(`${compareData.common_point_count} common points`);
  }

  return parts.join(' · ');
}
