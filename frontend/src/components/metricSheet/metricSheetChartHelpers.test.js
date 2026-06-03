import { describe, it, expect } from 'vitest';
import {
  buildYearlyReturnChartData,
  buildDrawdownChartData,
  buildDrawdownShadeRegions,
  drawdownRankOpacity,
} from './metricSheetChartHelpers';

describe('buildYearlyReturnChartData', () => {
  it('sorts backend yearly rows without computing returns', () => {
    const data = buildYearlyReturnChartData([
      { period: '2026', return: 0.05 },
      { period: '2024', return: -0.02 },
      { period: '2025', return: 0.143 },
    ]);
    expect(data.map((row) => row.period)).toEqual(['2024', '2025', '2026']);
    expect(data[1].return).toBe(0.143);
  });
});

describe('buildDrawdownChartData', () => {
  it('copies backend drawdown series values unchanged', () => {
    const data = buildDrawdownChartData([
      { date: '2025-01-01', drawdown: 0 },
      { date: '2025-01-02', drawdown: -0.012 },
    ]);
    expect(data).toEqual([
      { date: '2025-01-01', drawdown: 0 },
      { date: '2025-01-02', drawdown: -0.012 },
    ]);
  });
});

describe('buildDrawdownShadeRegions', () => {
  it('extends unrecovered episodes through series end date', () => {
    const regions = buildDrawdownShadeRegions(
      [
        {
          rank: 1,
          start_date: '2025-11-01',
          trough_date: '2025-12-15',
          recovery_date: null,
        },
      ],
      '2026-03-15'
    );
    expect(regions[0].end).toBe('2026-03-15');
    expect(regions[0].rank).toBe(1);
  });

  it('uses recovery_date when present', () => {
    const regions = buildDrawdownShadeRegions(
      [
        {
          rank: 2,
          start_date: '2025-06-10',
          trough_date: '2025-07-05',
          recovery_date: '2025-08-20',
        },
      ],
      '2026-03-15'
    );
    expect(regions[0].end).toBe('2025-08-20');
  });
});

describe('drawdownRankOpacity', () => {
  it('returns strongest opacity for rank 1 and lightest for rank 10', () => {
    expect(drawdownRankOpacity(1)).toBeGreaterThan(drawdownRankOpacity(10));
    expect(drawdownRankOpacity(1)).toBeCloseTo(0.35, 2);
    expect(drawdownRankOpacity(10)).toBeCloseTo(0.06, 2);
  });
});
