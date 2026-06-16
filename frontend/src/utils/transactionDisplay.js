/** Display helpers for transaction list rows — no finance calculations. */

export function isMutualFundTransaction(txn) {
  return txn?.asset_type === 'MUTUAL_FUND';
}

export function transactionSymbolLabel(txn) {
  if (!txn) return '';
  if (isMutualFundTransaction(txn)) {
    const name = txn.scheme_name || txn.scheme_code || txn.asset_symbol || '';
    const code = txn.scheme_code || txn.asset_symbol;
    if (name && code && name !== code) return `${name} (${code})`;
    return name || code || '';
  }
  return txn.asset_symbol || '';
}

export function transactionQuantity(txn) {
  if (!txn || txn.type === 'STOCK_SPLIT') return txn?.quantity;
  if (isMutualFundTransaction(txn)) {
    return txn.units_allotted ?? txn.quantity;
  }
  return txn.quantity;
}

export function transactionUnitPrice(txn) {
  if (!txn || txn.type === 'STOCK_SPLIT') return null;
  if (isMutualFundTransaction(txn)) {
    return txn.nav ?? txn.price_per_share;
  }
  return txn.price_per_share;
}

export function transactionLineTotal(txn) {
  if (!txn || txn.type === 'STOCK_SPLIT') return null;
  if (isMutualFundTransaction(txn)) {
    const paid = txn.paid_value;
    if (paid != null && !Number.isNaN(Number(paid))) return Number(paid);
    return null;
  }
  return Number(txn.quantity) * Number(txn.price_per_share) + Number(txn.fees || 0);
}

const NAV_STATUS_LABELS = {
  VERIFIED: 'NAV verified',
  NAV_MISSING: 'NAV not in cache',
  NAV_MISMATCH: 'NAV differs from cache',
  VALUE_MISMATCH: 'Market value mismatch',
  NOT_VERIFIED: 'Not verified',
  OK: 'OK',
  WARNING: 'Check NAV',
  UNCHECKED: 'Not checked',
};

export function navVerificationLabel(status) {
  if (!status) return null;
  return NAV_STATUS_LABELS[status] ?? String(status).replace(/_/g, ' ').toLowerCase();
}

export function navVerificationBadgeStatus(status) {
  if (!status) return null;
  const s = String(status).toUpperCase();
  if (s === 'VERIFIED' || s === 'OK') return 'verified';
  if (s === 'NAV_MISSING' || s === 'NAV_MISMATCH' || s === 'VALUE_MISMATCH' || s === 'WARNING') {
    return 'nav_warning';
  }
  return 'neutral';
}

export function holdingRowKey(h) {
  return h?.holding_key || h?.asset_symbol || '';
}

export function holdingSymbolLabel(h) {
  if (!h) return '';
  if (h.asset_type === 'BANK_CASH') {
    return h.bank_account_name || h.asset_symbol || 'Bank Cash';
  }
  if (h.asset_type === 'FIXED_DEPOSIT') {
    const inst = h.institution_name || 'Fixed Deposit';
    const acct = h.deposit_account_number;
    return acct ? `${inst} (${acct})` : inst;
  }
  if (h.asset_type === 'MUTUAL_FUND') {
    const name = h.scheme_name || h.scheme_code || h.asset_symbol || '';
    const code = h.scheme_code || h.asset_symbol;
    if (name && code && name !== code) return name;
    return name || code || '';
  }
  return h.asset_symbol || '';
}
