import { describe, it, expect } from 'vitest';
import {
  DISPLAY_CURRENCY_CHOICES,
  displayCurrencyForPortfolio,
} from './displayCurrency';

describe('displayCurrencyForPortfolio', () => {
  it('returns base currency when supported', () => {
    expect(displayCurrencyForPortfolio({ base_currency: 'INR' })).toBe('INR');
    expect(displayCurrencyForPortfolio({ base_currency: 'eur' })).toBe('EUR');
  });

  it('returns null for unsupported or missing base currency', () => {
    expect(displayCurrencyForPortfolio({ base_currency: 'JPY' })).toBeNull();
    expect(displayCurrencyForPortfolio({})).toBeNull();
    expect(displayCurrencyForPortfolio(null)).toBeNull();
  });

  it('exports supported display currency choices', () => {
    expect(DISPLAY_CURRENCY_CHOICES).toEqual(['EUR', 'USD', 'INR', 'GBP', 'CHF']);
  });
});
