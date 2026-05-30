import { describe, it, expect } from 'vitest';
import { buildCompareAssetOptions, isActiveHolding } from './compareHoldings';

describe('compareHoldings', () => {
  it('isActiveHolding treats closed and zero quantity as inactive', () => {
    expect(isActiveHolding({ holding_status: 'closed', quantity: 10 })).toBe(false);
    expect(isActiveHolding({ holding_status: 'open', quantity: 0 })).toBe(false);
    expect(isActiveHolding({ holding_status: 'open', quantity: 5 })).toBe(true);
  });

  it('prefers active row label when active and closed rows share a symbol', () => {
    const options = buildCompareAssetOptions([
      { asset_symbol: 'AAPL', quantity: 0, holding_status: 'closed' },
      { asset_symbol: 'AAPL', quantity: 10, holding_status: 'open' },
      { asset_symbol: 'MSFT', quantity: 0, holding_status: 'closed' },
    ]);
    expect(options.map((o) => o.symbol)).toEqual(['AAPL', 'MSFT']);
    expect(options[0]).toMatchObject({ symbol: 'AAPL', active: true, label: 'AAPL' });
    expect(options[1]).toMatchObject({ symbol: 'MSFT', active: false, label: 'MSFT (closed)' });
  });

  it('sorts active holdings before closed', () => {
    const options = buildCompareAssetOptions([
      { asset_symbol: 'ZZZ', quantity: 0, holding_status: 'closed' },
      { asset_symbol: 'AAA', quantity: 1, holding_status: 'open' },
    ]);
    expect(options[0].symbol).toBe('AAA');
    expect(options[1].symbol).toBe('ZZZ');
  });
});
