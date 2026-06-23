import { describe, it, expect } from 'vitest';
import {
  buildDashboardPerformanceChartConfig,
  findLatestValidChartReading,
  normalizePerformancePointValue,
} from './dashboardPerformanceChart';

describe('dashboardPerformanceChart', () => {
  it('preserves null performance point values without coercing to zero', () => {
    expect(normalizePerformancePointValue(null)).toBeNull();
    expect(normalizePerformancePointValue(undefined)).toBeNull();
    expect(normalizePerformancePointValue('')).toBeNull();
    expect(normalizePerformancePointValue(35982)).toBe(35982);
  });

  it('maps Value mode from fetchPortfolioPerformance array using value field', () => {
    const config = buildDashboardPerformanceChartConfig(
      [
        { date: '2026-01-01', value: 100000, metric: 'value', currency: 'EUR' },
        { date: '2026-01-02', value: 1840000, metric: 'value', currency: 'EUR' },
      ],
      { metric: 'value', chartMetricLabel: 'Value History', displayCurrency: 'EUR' }
    );
    expect(config.chartData).toEqual([
      { date: '2026-01-01', value: 100000, currency: 'EUR' },
      { date: '2026-01-02', value: 1840000, currency: 'EUR' },
    ]);
    expect(config.lines[0].dataKey).toBe('value');
  });

  it('maps Value mode from warnings wrapper using points array', () => {
    const config = buildDashboardPerformanceChartConfig(
      {
        points: [
          { date: '2026-05-01', value: 1800000, metric: 'value', currency: 'EUR' },
          { date: '2026-05-02', value: null, metric: 'value', currency: 'EUR' },
        ],
        warnings: ['FX unavailable'],
      },
      { metric: 'value', chartMetricLabel: 'Value History', displayCurrency: 'EUR' }
    );
    expect(config.chartData[1].value).toBeNull();
    expect(config.comparisonWarnings).toEqual(['FX unavailable']);
  });

  it('does not treat Value mode payload as benchmark comparison even if series key exists', () => {
    const config = buildDashboardPerformanceChartConfig(
      {
        points: [{ date: '2026-06-01', value: 1840000, metric: 'value', currency: 'EUR' }],
        series: [{ name: 'Portfolio', type: 'portfolio', data: [{ date: '2026-06-01', value: 35982 }] }],
      },
      { metric: 'value', chartMetricLabel: 'Value History', displayCurrency: 'EUR' }
    );
    expect(config.chartData).toEqual([
      { date: '2026-06-01', value: 1840000, currency: 'EUR' },
    ]);
    expect(config.lines[0].dataKey).toBe('value');
  });

  it('findLatestValidChartReading skips trailing null points', () => {
    const reading = findLatestValidChartReading(
      [
        { date: '2026-05-01', value: 1800000 },
        { date: '2026-05-02', value: null },
        { date: '2026-05-03', value: null },
      ],
      'value'
    );
    expect(reading).toEqual({ date: '2026-05-01', value: 1800000 });
  });

  it('findLatestValidChartReading uses the latest valid point in chronological order', () => {
    const reading = findLatestValidChartReading(
      [
        { date: '2026-05-01', value: 35982 },
        { date: '2026-05-02', value: 1840000 },
      ],
      'value'
    );
    expect(reading).toEqual({ date: '2026-05-02', value: 1840000 });
  });

  it('uses comparison series only for return metrics with series payload', () => {
    const config = buildDashboardPerformanceChartConfig(
      {
        metric: 'cumulative_return',
        series: [
          { type: 'portfolio', name: 'Portfolio', data: [{ date: '2026-01-01', value: 0 }] },
          { type: 'benchmark', name: 'S&P 500', data: [{ date: '2026-01-01', value: 0 }] },
        ],
        warnings: [],
      },
      {
        metric: 'cumulative_return',
        chartMetricLabel: 'Cumulative Return %',
        displayCurrency: 'EUR',
      }
    );
    expect(config.chartData[0]).toMatchObject({ date: '2026-01-01', Portfolio: 0, 'S&P 500': 0 });
    expect(config.lines).toHaveLength(2);
  });
});
