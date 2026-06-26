/** Supported display currencies in the app shell (must match Layout selector). */
export const DISPLAY_CURRENCY_CHOICES = ['EUR', 'USD', 'INR', 'GBP', 'CHF'];

/** Return portfolio base currency when it is a supported display currency, else null. */
export function displayCurrencyForPortfolio(portfolio) {
  const base = String(portfolio?.base_currency || '').toUpperCase();
  if (!base || !DISPLAY_CURRENCY_CHOICES.includes(base)) return null;
  return base;
}
