/**
 * Build cash deposit payload for BUY shortfall add-and-continue (Cash-4C).
 * Uses backend shortfall amount/currency only — no React balance math.
 */

export function purchaseSymbolFromForm(form, isMutualFund) {
  if (isMutualFund) {
    return String(form.scheme_code || form.scheme_name || '').trim();
  }
  return String(form.asset_symbol || '').trim();
}

export function depositDateForPurchase(form, isMutualFund) {
  if (isMutualFund) {
    return form.investment_date || form.nav_date || '';
  }
  return form.date || '';
}

export function buildShortfallDepositPayload(
  shortfall,
  form,
  isMutualFund,
  { sourceOfFunds = '', note = '' } = {}
) {
  const symbol = purchaseSymbolFromForm(form, isMutualFund);
  const defaultNote = symbol ? `Added before purchase of ${symbol}` : '';
  return {
    portfolio_id: Number(form.portfolio_id),
    date: depositDateForPurchase(form, isMutualFund),
    currency: shortfall.currency,
    amount: shortfall.shortfall,
    source_of_funds: sourceOfFunds || '',
    note: String(note ?? '').trim() || defaultNote,
  };
}
