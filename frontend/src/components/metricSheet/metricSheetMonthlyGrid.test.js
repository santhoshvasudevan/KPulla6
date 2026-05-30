import { describe, it, expect } from 'vitest';
import { buildMonthlyReturnsGrid, MONTH_LABELS } from './metricSheetMonthlyGrid';

describe('buildMonthlyReturnsGrid', () => {
  it('organizes backend monthly rows by year and month without computing returns', () => {
    const rows = buildMonthlyReturnsGrid(
      [
        { period: '2026-01', return: 0.021 },
        { period: '2026-02', return: -0.012 },
      ],
      [{ period: '2026', return: 0.143 }]
    );

    expect(rows).toHaveLength(1);
    expect(rows[0].year).toBe('2026');
    expect(rows[0].months).toHaveLength(12);
    expect(rows[0].months[0]).toMatchObject({ label: 'Jan', return: 0.021 });
    expect(rows[0].months[1]).toMatchObject({ label: 'Feb', return: -0.012 });
    expect(rows[0].months[2].return).toBeNull();
    expect(rows[0].yearlyReturn).toBe(0.143);
  });

  it('includes year row from yearly returns when monthly is sparse', () => {
    const rows = buildMonthlyReturnsGrid(
      [{ period: '2025-11', return: 0.05 }],
      [
        { period: '2025', return: 0.08 },
        { period: '2026', return: 0.02 },
      ]
    );

    expect(rows.map((r) => r.year)).toEqual(['2025', '2026']);
    expect(rows[0].yearlyReturn).toBe(0.08);
    expect(rows[1].months.every((m) => m.return === null)).toBe(true);
    expect(rows[1].yearlyReturn).toBe(0.02);
  });

  it('returns empty array when both inputs are empty', () => {
    expect(buildMonthlyReturnsGrid([], [])).toEqual([]);
  });

  it('covers all month column labels', () => {
    expect(MONTH_LABELS).toHaveLength(12);
  });
});
