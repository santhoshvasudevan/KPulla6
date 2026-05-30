/** Display-only formatters for Metric Sheet API values (fractions/ratios from backend). */

export const METRIC_EM_DASH = '—';

export function formatMetricPercentFraction(value, { showSign = false } = {}) {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return METRIC_EM_DASH;
  }
  const num = Number(value);
  const pct = (Math.abs(num) * 100).toFixed(2);
  if (showSign && num > 0) return `+${pct}%`;
  if (showSign && num < 0) return `−${pct}%`;
  if (num < 0) return `−${pct}%`;
  return `${pct}%`;
}

export function formatMetricRatio(value, decimals = 2) {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return METRIC_EM_DASH;
  }
  return Number(value).toFixed(decimals);
}

export function formatMetricNumber(value, decimals = 0) {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return METRIC_EM_DASH;
  }
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Number(value));
}

export function formatMetricDays(value) {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return METRIC_EM_DASH;
  }
  const n = Math.round(Number(value));
  if (n === 1) return '1 day';
  return `${n} days`;
}

/** Map signed fractional return to MetricCard tone (display only). */
export function metricFractionTone(value) {
  if (value == null || value === '' || Number.isNaN(Number(value))) return 'neutral';
  const num = Number(value);
  if (num > 0) return 'positive';
  if (num < 0) return 'negative';
  return 'neutral';
}
