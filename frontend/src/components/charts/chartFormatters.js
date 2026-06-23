import { formatCurrency } from '../../utils/formatters';
import { formatMetricPercentFraction, METRIC_EM_DASH } from '../../utils/metricFormatters';

/** Display-only tooltip value formatting. No finance calculations. */

export function formatChartTooltipCurrency(value, currency = 'EUR') {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return METRIC_EM_DASH;
  }
  return formatCurrency(value, currency);
}

export function formatChartTooltipPercent(value, { showSign = false } = {}) {
  return formatMetricPercentFraction(value, { showSign });
}

export function formatChartTooltipValue(value, { kind = 'number', currency, showSign = false } = {}) {
  if (kind === 'currency') {
    return formatChartTooltipCurrency(value, currency);
  }
  if (kind === 'percent') {
    return formatChartTooltipPercent(value, { showSign });
  }
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return METRIC_EM_DASH;
  }
  return String(value);
}
