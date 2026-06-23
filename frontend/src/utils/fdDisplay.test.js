import { describe, it, expect } from 'vitest';
import { fdPayoutLabel, fdStatusBadgeProps, fdStatusCounts } from './fdDisplay';

describe('fdDisplay', () => {
  it('maps backend FD status to badge props', () => {
    expect(fdStatusBadgeProps('ACTIVE')).toEqual({ status: 'ok', label: 'Active' });
    expect(fdStatusBadgeProps('MATURED')).toEqual({ status: 'warning', label: 'Matured' });
    expect(fdStatusBadgeProps('MATURED_SETTLED')).toEqual({ status: 'info', label: 'Settled' });
    expect(fdStatusBadgeProps('CLOSED')).toEqual({ status: 'closed', label: 'Closed' });
  });

  it('formats payout frequency labels', () => {
    expect(fdPayoutLabel('QUARTERLY')).toBe('Quarterly');
    expect(fdPayoutLabel('COMPOUNDED')).toBe('Compounded');
  });

  it('counts FD rows by backend status only', () => {
    const items = [
      { status: 'ACTIVE' },
      { status: 'MATURED' },
      { status: 'MATURED_SETTLED' },
      { status: 'CLOSED' },
    ];
    expect(fdStatusCounts(items)).toEqual({
      total: 4,
      active: 1,
      matured: 1,
      settled: 2,
    });
  });
});
