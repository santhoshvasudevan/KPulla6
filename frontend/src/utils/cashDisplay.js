import { formatCurrency } from './formatters';

const ENTRY_TYPE_LABELS = {
  CASH_DEPOSIT: 'Deposit',
  CASH_WITHDRAWAL: 'Withdrawal',
  BUY_SETTLEMENT: 'Buy settlement',
  SELL_SETTLEMENT: 'Sell settlement',
  TAX_WITHHELD: 'Tax withheld',
  DIVIDEND_CASH: 'Dividend (cash)',
  INTEREST: 'Interest',
  FEE: 'Fee',
  TAX: 'Tax',
  ADJUSTMENT: 'Adjustment',
  TRANSFER_OUT: 'Transfer out',
  TRANSFER_IN: 'Transfer in',
  FX_CONVERSION_OUT: 'FX conversion out',
  FX_CONVERSION_IN: 'FX conversion in',
};

export function cashEntryTypeLabel(entryType) {
  if (!entryType) return '—';
  return ENTRY_TYPE_LABELS[entryType] || entryType.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Display formatting only — does not compute balances. */
export function formatCashAmount(value, currency) {
  return formatCurrency(value, currency);
}

/** Manual CASH_DEPOSIT / CASH_WITHDRAWAL without links — editable in Cash-3D. */
export function isManualEditableCashEntry(entry) {
  if (!entry) return false;
  const type = entry.entry_type;
  if (type !== 'CASH_DEPOSIT' && type !== 'CASH_WITHDRAWAL') return false;
  if (entry.linked_transaction_id != null) return false;
  if (entry.transfer_group_id != null) return false;
  return true;
}

export function amountTone(amount) {
  const n = Number(amount);
  if (Number.isNaN(n) || n === 0) return 'neutral';
  return n > 0 ? 'gain' : 'loss';
}

export const LEDGER_ENTRY_TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'CASH_DEPOSIT', label: 'Deposit' },
  { value: 'CASH_WITHDRAWAL', label: 'Withdrawal' },
  { value: 'BUY_SETTLEMENT', label: 'Buy settlement' },
  { value: 'SELL_SETTLEMENT', label: 'Sell settlement' },
  { value: 'TAX_WITHHELD', label: 'Tax withheld' },
  { value: 'DIVIDEND_CASH', label: 'Dividend (cash)' },
  { value: 'INTEREST', label: 'Interest' },
  { value: 'FEE', label: 'Fee' },
  { value: 'TAX', label: 'Tax' },
  { value: 'ADJUSTMENT', label: 'Adjustment' },
  { value: 'TRANSFER_OUT', label: 'Transfer out' },
  { value: 'TRANSFER_IN', label: 'Transfer in' },
  { value: 'FX_CONVERSION_OUT', label: 'FX conversion out' },
  { value: 'FX_CONVERSION_IN', label: 'FX conversion in' },
];
