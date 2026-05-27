import { describe, it, expect } from 'vitest';
import {
  buildStockUpdatePayload,
  buildMutualFundUpdatePayload,
  buildTransactionUpdatePayload,
} from './transactionPayload';

describe('transactionPayload', () => {
  it('preserves STOCK_SPLIT split_from and split_to on reassignment', () => {
    const txn = {
      id: 5,
      asset_symbol: 'GOOG',
      date: '2022-07-15',
      type: 'STOCK_SPLIT',
      quantity: 0,
      price_per_share: 0,
      currency: 'EUR',
      fees: 0,
      split_from: 1,
      split_to: 20,
      portfolio_id: 1,
    };
    const payload = buildTransactionUpdatePayload(txn, 2);
    expect(payload.portfolio_id).toBe(2);
    expect(payload.split_from).toBe(1);
    expect(payload.split_to).toBe(20);
    expect(payload.quantity).toBe(0);
    expect(payload.price_per_share).toBe(0);
  });

  it('builds mutual fund payload with all required fields', () => {
    const txn = {
      asset_type: 'MUTUAL_FUND',
      asset_symbol: '120503',
      scheme_code: '120503',
      scheme_name: 'Test Fund',
      folio_number: 'F1',
      type: 'BUY',
      investment_date: '2026-01-01',
      nav_date: '2026-01-02',
      nav: 42.5,
      units_allotted: 100,
      paid_value: 4255,
      market_value: 4250,
      fees: 5,
      currency: 'INR',
      portfolio_id: 1,
    };
    const payload = buildMutualFundUpdatePayload(txn, 3);
    expect(payload.asset_type).toBe('MUTUAL_FUND');
    expect(payload.portfolio_id).toBe(3);
    expect(payload.scheme_code).toBe('120503');
    expect(payload.folio_number).toBe('F1');
    expect(payload.nav).toBe(42.5);
  });

  it('routes stock vs MF through buildTransactionUpdatePayload', () => {
    const stock = { asset_symbol: 'AAPL', date: '2026-01-01', type: 'BUY', quantity: 1, price_per_share: 100, currency: 'USD', fees: 0, portfolio_id: 1 };
    expect(buildTransactionUpdatePayload(stock, 2).asset_symbol).toBe('AAPL');
    const mf = { asset_type: 'MUTUAL_FUND', asset_symbol: '1', scheme_code: '1', scheme_name: 'X', folio_number: 'F', type: 'BUY', investment_date: '2026-01-01', nav_date: '2026-01-01', nav: 10, units_allotted: 1, paid_value: 10, market_value: 10, portfolio_id: 1 };
    expect(buildTransactionUpdatePayload(mf, 2).asset_type).toBe('MUTUAL_FUND');
  });
});
