/** Display-only heatmap tone mapping for monthly return fractions (not finance math). */

export const MONTHLY_HEATMAP_THRESHOLDS = {
  strongNegative: -0.1,
  softNegative: -0.03,
  softPositive: 0.03,
  strongPositive: 0.1,
};

/**
 * Map a backend monthly return fraction to a heatmap cell tone class suffix.
 * @returns {'missing'|'strong-negative'|'soft-negative'|'neutral'|'soft-positive'|'strong-positive'}
 */
export function monthlyHeatmapTone(value) {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return 'missing';
  }
  const n = Number(value);
  if (n <= MONTHLY_HEATMAP_THRESHOLDS.strongNegative) return 'strong-negative';
  if (n < MONTHLY_HEATMAP_THRESHOLDS.softNegative) return 'soft-negative';
  if (n <= MONTHLY_HEATMAP_THRESHOLDS.softPositive) return 'neutral';
  if (n < MONTHLY_HEATMAP_THRESHOLDS.strongPositive) return 'soft-positive';
  return 'strong-positive';
}

export function monthlyHeatmapToneClass(value) {
  const tone = monthlyHeatmapTone(value);
  return `metric-sheet-monthly-grid__cell--${tone}`;
}
