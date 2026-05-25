/**
 * Format a number as currency with 2 decimal places.
 * Uses 'en-US' locale explicitly for consistency across environments.
 */
export function currencyPrefix(currency) {
  const c = (currency || 'EUR').toUpperCase();
  if (c === 'EUR') return '€';
  if (c === 'USD') return '$';
  if (c === 'INR') return '₹';
  if (c === 'GBP') return '£';
  if (c === 'CHF') return 'CHF ';
  return `${c} `;
}

export function formatCurrency(val, currency = 'EUR') {
  return `${currencyPrefix(currency)}${new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(val))}`;
}

/**
 * Format a decimal fraction as a percentage string, e.g. 0.125 → "+12.50%"
 */
export function formatPercent(val) {
  return (Number(val) * 100).toFixed(2) + '%';
}
