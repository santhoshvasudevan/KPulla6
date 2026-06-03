/** Display-only comparison of two backend metric values for Compare highlighting. */

export const COMPARE_HIGHLIGHT = {
  BETTER: 'better',
  WORSE: 'worse',
  TIE: 'tie',
  NEUTRAL: 'neutral',
  UNKNOWN: 'unknown',
};

export const COMPARE_HIGHLIGHT_LABELS = {
  [COMPARE_HIGHLIGHT.BETTER]: 'Best value in this row',
  [COMPARE_HIGHLIGHT.WORSE]: 'Lower value in this row',
  [COMPARE_HIGHLIGHT.TIE]: 'Equal values',
};

/** @typedef {'higher' | 'lower' | 'less_negative' | 'neutral' | 'unknown'} MetricCompareDirection */

/** @type {Record<string, MetricCompareDirection>} */
export const METRIC_COMPARE_DIRECTION = {
  cumulative_return: 'higher',
  cagr: 'higher',
  twror: 'higher',
  xirr: 'higher',
  sharpe_ratio: 'higher',
  sortino_ratio: 'higher',
  calmar_ratio: 'higher',
  win_rate: 'higher',
  average_daily_return: 'higher',
  alpha: 'higher',
  active_return: 'higher',
  information_ratio: 'higher',
  treynor_ratio: 'higher',
  volatility_annualized: 'lower',
  downside_deviation: 'lower',
  max_drawdown: 'less_negative',
  tracking_error: 'neutral',
  beta: 'neutral',
  correlation: 'neutral',
  paired_count: 'neutral',
  days: 'neutral',
};

export const COMPARE_EQUAL_TOLERANCE = 1e-9;

function parseComparableValue(value) {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return null;
  }
  return Number(value);
}

/**
 * @param {string} metricKey
 * @returns {MetricCompareDirection}
 */
export function getMetricCompareDirection(metricKey) {
  return METRIC_COMPARE_DIRECTION[metricKey] ?? 'unknown';
}

/**
 * Highlight state for exactly two subject values (display only).
 *
 * @param {string} metricKey
 * @param {[unknown, unknown]} values
 * @returns {[string, string]}
 */
export function getCompareHighlightStates(metricKey, values) {
  if (!Array.isArray(values) || values.length !== 2) {
    return [COMPARE_HIGHLIGHT.UNKNOWN, COMPARE_HIGHLIGHT.UNKNOWN];
  }

  const direction = getMetricCompareDirection(metricKey);
  if (direction === 'neutral' || direction === 'unknown') {
    return [COMPARE_HIGHLIGHT.NEUTRAL, COMPARE_HIGHLIGHT.NEUTRAL];
  }

  const parsed = values.map(parseComparableValue);
  if (parsed.some((value) => value == null)) {
    return [COMPARE_HIGHLIGHT.NEUTRAL, COMPARE_HIGHLIGHT.NEUTRAL];
  }

  const [left, right] = parsed;
  if (Math.abs(left - right) <= COMPARE_EQUAL_TOLERANCE) {
    return [COMPARE_HIGHLIGHT.TIE, COMPARE_HIGHLIGHT.TIE];
  }

  let leftBetter;
  if (direction === 'higher') {
    leftBetter = left > right;
  } else if (direction === 'lower') {
    leftBetter = left < right;
  } else if (direction === 'less_negative') {
    leftBetter = left > right;
  }

  return leftBetter
    ? [COMPARE_HIGHLIGHT.BETTER, COMPARE_HIGHLIGHT.WORSE]
    : [COMPARE_HIGHLIGHT.WORSE, COMPARE_HIGHLIGHT.BETTER];
}
