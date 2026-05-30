import { describe, it, expect } from 'vitest';
import {
  METRIC_EM_DASH,
  formatMetricPercentFraction,
  formatMetricRatio,
  formatMetricNumber,
  formatMetricDays,
  metricFractionTone,
} from './metricFormatters';

describe('metricFormatters', () => {
  it('formatMetricPercentFraction converts fractions to percent', () => {
    expect(formatMetricPercentFraction(0.1234)).toBe('12.34%');
    expect(formatMetricPercentFraction(-0.05)).toBe('−5.00%');
    expect(formatMetricPercentFraction(0.1234, { showSign: true })).toBe('+12.34%');
  });

  it('formatMetricPercentFraction returns em dash for null', () => {
    expect(formatMetricPercentFraction(null)).toBe(METRIC_EM_DASH);
    expect(formatMetricPercentFraction(undefined)).toBe(METRIC_EM_DASH);
  });

  it('formatMetricRatio formats plain ratios', () => {
    expect(formatMetricRatio(1.234)).toBe('1.23');
    expect(formatMetricRatio(null)).toBe(METRIC_EM_DASH);
  });

  it('formatMetricNumber formats counts', () => {
    expect(formatMetricNumber(42)).toBe('42');
    expect(formatMetricNumber(null)).toBe(METRIC_EM_DASH);
  });

  it('formatMetricDays formats day counts', () => {
    expect(formatMetricDays(1)).toBe('1 day');
    expect(formatMetricDays(14)).toBe('14 days');
    expect(formatMetricDays(null)).toBe(METRIC_EM_DASH);
  });

  it('metricFractionTone maps sign to card tone', () => {
    expect(metricFractionTone(0.1)).toBe('positive');
    expect(metricFractionTone(-0.1)).toBe('negative');
    expect(metricFractionTone(null)).toBe('neutral');
  });
});
