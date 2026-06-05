import { describe, it, expect } from 'vitest';
import {
  buildShortfallDepositPayload,
  depositDateForPurchase,
} from './purchaseShortfallHelpers';

describe('purchaseShortfallHelpers', () => {
  const shortfall = { currency: 'EUR', shortfall: 505, required: 1005, available: 500 };

  it('uses backend shortfall amount and currency for stock BUY', () => {
    const payload = buildShortfallDepositPayload(
      shortfall,
      {
        portfolio_id: '1',
        date: '2026-06-01',
        asset_symbol: 'AAPL',
        currency: 'USD',
      },
      false,
      { sourceOfFunds: 'Salary', note: '' }
    );
    expect(payload).toEqual({
      portfolio_id: 1,
      date: '2026-06-01',
      currency: 'EUR',
      amount: 505,
      source_of_funds: 'Salary',
      note: 'Added before purchase of AAPL',
    });
  });

  it('MF BUY deposit date uses investment_date', () => {
    expect(
      depositDateForPurchase(
        { investment_date: '2026-03-10', nav_date: '2026-03-15' },
        true
      )
    ).toBe('2026-03-10');
    const payload = buildShortfallDepositPayload(
      { currency: 'INR', shortfall: 100 },
      {
        portfolio_id: '2',
        investment_date: '2026-03-10',
        nav_date: '2026-03-15',
        scheme_code: '120503',
      },
      true
    );
    expect(payload.date).toBe('2026-03-10');
    expect(payload.currency).toBe('INR');
    expect(payload.amount).toBe(100);
  });
});
