const PAYOUT_LABELS = {
  MONTHLY: 'Monthly',
  QUARTERLY: 'Quarterly',
  HALF_YEARLY: 'Half yearly',
  ANNUALLY: 'Annually',
  COMPOUNDED: 'Compounded',
};

const STATUS_LABELS = {
  ACTIVE: 'Active',
  MATURED: 'Matured',
  MATURED_SETTLED: 'Settled',
  CLOSED: 'Closed',
  CANCELLED: 'Cancelled',
};

export const FD_ESTIMATE_TYPE_COMPOUNDED = 'COMPOUNDED_MATURITY';
export const FD_ESTIMATE_TYPE_PAYOUT = 'PAYOUT_INTEREST';

/** Display-only status badge mapping from backend FD status. */
export function fdStatusBadgeProps(status) {
  switch (status) {
    case 'ACTIVE':
      return { status: 'ok', label: STATUS_LABELS.ACTIVE };
    case 'MATURED':
      return { status: 'warning', label: STATUS_LABELS.MATURED };
    case 'MATURED_SETTLED':
      return { status: 'info', label: STATUS_LABELS.MATURED_SETTLED };
    case 'CLOSED':
      return { status: 'closed', label: STATUS_LABELS.CLOSED };
    case 'CANCELLED':
      return { status: 'closed', label: STATUS_LABELS.CANCELLED };
    default:
      return { status: 'neutral', label: status || '—' };
  }
}

export function fdPayoutLabel(frequency) {
  if (!frequency) return '—';
  return PAYOUT_LABELS[frequency] || frequency.replace(/_/g, ' ').toLowerCase();
}

export function fdIsCompounded(fd) {
  return fd?.interest_payout_frequency === 'COMPOUNDED' || fd?.estimate_type === FD_ESTIMATE_TYPE_COMPOUNDED;
}

export function fdIsPayout(fd) {
  return (
    fd?.estimate_type === FD_ESTIMATE_TYPE_PAYOUT ||
    (fd?.interest_payout_frequency &&
      fd.interest_payout_frequency !== 'COMPOUNDED' &&
      Boolean(PAYOUT_LABELS[fd.interest_payout_frequency]))
  );
}

/** Resolved maturity value for holdings display (expected, else estimated). */
export function fdDisplayMaturityValue(fd) {
  if (fdIsPayout(fd)) {
    if (fd?.maturity_value_source === 'USER_CONFIRMED' && fd?.expected_maturity_value != null) {
      return fd.expected_maturity_value;
    }
    return fd?.principal_amount ?? fd?.expected_maturity_value ?? fd?.estimated_maturity_value ?? null;
  }
  if (fd?.expected_maturity_value != null) return fd.expected_maturity_value;
  if (fd?.estimated_maturity_value != null) return fd.estimated_maturity_value;
  return null;
}

export function fdDisplayTotalInterest(fd) {
  if (fd?.estimated_total_interest != null) return fd.estimated_total_interest;
  if (fd?.expected_interest != null) return fd.expected_interest;
  if (fd?.estimated_interest != null) return fd.estimated_interest;
  return null;
}

export function fdDisplayPeriodicInterest(fd) {
  return fd?.estimated_periodic_interest ?? null;
}

/** @deprecated use fdDisplayTotalInterest for payout-aware display */
export function fdDisplayMaturityInterest(fd) {
  if (fdIsPayout(fd)) return fdDisplayTotalInterest(fd);
  if (fd?.expected_interest != null) return fd.expected_interest;
  if (fd?.estimated_interest != null) return fd.estimated_interest;
  return null;
}

export function fdDisplayMaturitySource(fd) {
  if (fd?.maturity_value_source) return fd.maturity_value_source;
  if (fdIsPayout(fd)) return 'AUTO_PRINCIPAL';
  if (fdDisplayMaturityValue(fd) != null) return 'AUTO_ESTIMATE';
  return null;
}

export function fdMaturityValueSourceLabel(source) {
  if (source === 'USER_CONFIRMED') return 'User confirmed';
  if (source === 'AUTO_ESTIMATE') return 'Auto estimate';
  if (source === 'AUTO_PRINCIPAL') return 'Principal returned';
  return '—';
}

export function fdMaturityValueSourceBadgeProps(source, fd = null) {
  if (source === 'USER_CONFIRMED') {
    return { status: 'info', label: 'User confirmed' };
  }
  if (source === 'AUTO_PRINCIPAL' || (fd && fdIsPayout(fd) && source !== 'USER_CONFIRMED')) {
    return { status: 'neutral', label: 'Principal returned' };
  }
  if (source === 'AUTO_ESTIMATE') {
    return { status: 'neutral', label: 'Auto estimate' };
  }
  return { status: 'neutral', label: 'Not estimated' };
}

/** Display-only counts by backend status — no finance math. */
export function fdStatusCounts(items = []) {
  const counts = { total: items.length, active: 0, matured: 0, settled: 0 };
  for (const fd of items) {
    if (fd.status === 'ACTIVE') counts.active += 1;
    else if (fd.status === 'MATURED') counts.matured += 1;
    else if (fd.status === 'CLOSED' || fd.status === 'MATURED_SETTLED') counts.settled += 1;
  }
  return counts;
}
