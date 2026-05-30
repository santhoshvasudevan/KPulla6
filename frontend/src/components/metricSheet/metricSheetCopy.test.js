import { describe, it, expect } from 'vitest';
import {
  formatCompareRangeContext,
  METRIC_SHEET_XIRR_FULL_SCOPE_NOTE,
} from './metricSheetCopy';

describe('metricSheetCopy', () => {
  it('formats requested range and common dates', () => {
    const text = formatCompareRangeContext('3Y', {
      range: { code: '3Y', start: '2023-05-30', end: '2026-05-30' },
      common_start_date: '2024-01-05',
      common_end_date: '2026-05-30',
      common_point_count: 400,
    });
    expect(text).toBe(
      'Requested range: 3Y · Compared over common dates: 2024-01-05 to 2026-05-30 · 400 common points'
    );
  });

  it('exports XIRR full-scope note copy', () => {
    expect(METRIC_SHEET_XIRR_FULL_SCOPE_NOTE).toMatch(/full-scope/i);
    expect(METRIC_SHEET_XIRR_FULL_SCOPE_NOTE).toMatch(/selected range/i);
  });
});
