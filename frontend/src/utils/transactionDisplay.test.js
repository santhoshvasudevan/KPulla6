import { describe, it, expect } from 'vitest';
import {
  isMutualFundTransaction,
  transactionSymbolLabel,
  transactionQuantity,
  transactionUnitPrice,
  transactionLineTotal,
  navVerificationLabel,
  navVerificationBadgeStatus,
  navReviewLabel,
  navReviewBadgeStatus,
  holdingRowKey,
  holdingSymbolLabel,
  holdingAssetClassVariant,
} from './transactionDisplay';

describe('transactionDisplay', () => {
  it('detects mutual fund transactions', () => {
    expect(isMutualFundTransaction({ asset_type: 'MUTUAL_FUND' })).toBe(true);
    expect(isMutualFundTransaction({ asset_symbol: 'AAPL' })).toBe(false);
  });

  it('formats MF symbol with scheme name and code', () => {
    const txn = {
      asset_type: 'MUTUAL_FUND',
      scheme_name: 'Test Fund',
      scheme_code: '120503',
    };
    expect(transactionSymbolLabel(txn)).toBe('Test Fund (120503)');
  });

  it('uses units and nav for MF quantity and price', () => {
    const txn = {
      asset_type: 'MUTUAL_FUND',
      type: 'BUY',
      units_allotted: 50,
      nav: 42.5,
      quantity: 50,
      price_per_share: 42.5,
      paid_value: 2125,
    };
    expect(transactionQuantity(txn)).toBe(50);
    expect(transactionUnitPrice(txn)).toBe(42.5);
    expect(transactionLineTotal(txn)).toBe(2125);
  });

  it('keeps stock line total calculation', () => {
    const txn = { type: 'BUY', quantity: 10, price_per_share: 150, fees: 2.5 };
    expect(transactionLineTotal(txn)).toBe(1502.5);
  });

  it('maps nav verification statuses calmly', () => {
    expect(navVerificationLabel('VERIFIED')).toBe('NAV verified');
    expect(navVerificationLabel('NAV_MISSING')).toBe('NAV not in cache');
    expect(navVerificationBadgeStatus('VERIFIED')).toBe('verified');
    expect(navVerificationBadgeStatus('NAV_MISMATCH')).toBe('nav_warning');
  });

  it('distinguishes read-only NAV review states from the API', () => {
    const review = (reviewClass, extra = {}) => ({ nav_review: { review_class: reviewClass }, ...extra });
    expect(navReviewLabel({ nav_review: null })).toBeNull();
    expect(navReviewBadgeStatus({})).toBeNull();
    expect(navReviewLabel(review('provisional'))).toBe('Provisional NAV — awaiting provider');
    expect(navReviewLabel(review('legacy'))).toBe('Legacy NAV — no provider NAV');
    expect(navReviewLabel(review('missing'))).toBe('Provider NAV no longer cached');
    expect(navReviewLabel(review('cached_discrepancy', { nav_provisional: true })))
      .toBe('Provider NAV now available — review');
    expect(navReviewLabel(review('cached_discrepancy'))).toBe('Cached NAV differs — review');
    expect(navReviewBadgeStatus(review('provisional'))).toBe('warning');
    expect(navReviewBadgeStatus(review('cached_discrepancy'))).toBe('warning');
    expect(navReviewBadgeStatus(review('legacy'))).toBe('neutral');
  });

  it('formats MF holding labels and keys', () => {
    const h = {
      asset_type: 'MUTUAL_FUND',
      holding_key: '120503:F1',
      scheme_name: 'Growth Fund',
      scheme_code: '120503',
    };
    expect(holdingRowKey(h)).toBe('120503:F1');
    expect(holdingSymbolLabel(h)).toBe('Growth Fund');
  });

  it('maps holding asset class pill variants', () => {
    expect(holdingAssetClassVariant({ asset_type: 'MUTUAL_FUND' })).toBe('mutualFund');
    expect(holdingAssetClassVariant({ asset_type: 'FIXED_DEPOSIT' })).toBe('fixedDeposit');
    expect(holdingAssetClassVariant({ asset_type: 'BANK_CASH' })).toBe('cash');
    expect(holdingAssetClassVariant({ asset_symbol: 'AAPL' })).toBe('stock');
  });
});
