import { isMutualFundTransaction } from './transactionDisplay';

/** Build a full stock PUT payload from an API transaction row. */
export function buildStockUpdatePayload(txn, portfolioIdOverride) {
  const isStockSplit = txn.type === 'STOCK_SPLIT';
  return {
    asset_symbol: txn.asset_symbol,
    date: txn.date,
    type: txn.type,
    currency: txn.currency,
    portfolio_id: portfolioIdOverride != null ? portfolioIdOverride : txn.portfolio_id,
    quantity: isStockSplit ? 0 : txn.quantity,
    price_per_share: isStockSplit ? 0 : txn.price_per_share,
    fees: isStockSplit ? 0 : txn.fees ?? 0,
    split_from: isStockSplit ? txn.split_from : null,
    split_to: isStockSplit ? txn.split_to : null,
  };
}

/** Build a full mutual fund PUT payload from an API transaction row. */
export function buildMutualFundUpdatePayload(txn, portfolioIdOverride) {
  const payload = {
    asset_type: 'MUTUAL_FUND',
    scheme_code: txn.scheme_code || txn.asset_symbol,
    scheme_name: txn.scheme_name || '',
    folio_number: txn.folio_number || '',
    type: txn.type,
    investment_date: txn.investment_date || txn.date,
    nav_date: txn.nav_date || txn.date,
    nav: txn.nav ?? txn.price_per_share,
    units_allotted: txn.units_allotted ?? txn.quantity,
    paid_value: txn.paid_value,
    market_value: txn.market_value,
    currency: txn.currency || 'INR',
    portfolio_id: portfolioIdOverride != null ? portfolioIdOverride : txn.portfolio_id,
  };
  if (txn.fees != null) payload.fees = txn.fees;
  const optionalStrings = [
    'fund_house',
    'scheme_type',
    'scheme_category',
    'direct_or_regular',
    'growth_or_idcw',
  ];
  for (const key of optionalStrings) {
    const v = txn[key];
    if (v != null && String(v).trim()) payload[key] = String(v).trim();
  }
  return payload;
}

/** Build a full transaction PUT payload, optionally overriding portfolio_id. */
export function buildTransactionUpdatePayload(txn, portfolioIdOverride) {
  if (isMutualFundTransaction(txn)) {
    return buildMutualFundUpdatePayload(txn, portfolioIdOverride);
  }
  return buildStockUpdatePayload(txn, portfolioIdOverride);
}
