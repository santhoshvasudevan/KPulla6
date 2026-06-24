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
