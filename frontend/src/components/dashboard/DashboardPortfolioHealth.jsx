import { AppCard, StatusBadge } from '../ui';

const STATUS_LABELS = {
  success: 'Good',
  warning: 'Review',
  info: 'Info',
  neutral: 'Current',
};

/** Build review-queue rows from backend warnings/status fields only. */
export function buildPortfolioHealthItems({
  summary,
  comparisonWarnings = [],
  metricSheetWarnings = [],
}) {
  const items = [];

  if (summary?.fx_status === 'fx_unavailable') {
    items.push({
      id: 'fx-status',
      label: 'FX availability',
      status: 'warning',
      detail: 'FX unavailable for one or more dates.',
    });
  }

  if (summary?.has_fixed_deposits) {
    items.push({
      id: 'fixed-deposits',
      label: 'Fixed deposits',
      status: 'info',
      detail: 'Value and return metrics include Fixed Deposits where applicable.',
    });
  }

  if (summary?.cash_summary?.total_display_value > 0) {
    items.push({
      id: 'cash-included',
      label: 'Cash included',
      status: 'success',
      detail: 'Portfolio value includes ledger cash balances from the API.',
    });
  }

  (summary?.warnings || []).forEach((warning, index) => {
    items.push({
      id: `summary-warning-${index}`,
      label: 'Portfolio review',
      status: 'warning',
      detail: warning,
    });
  });

  comparisonWarnings.forEach((warning, index) => {
    items.push({
      id: `performance-warning-${index}`,
      label: 'Performance data',
      status: 'warning',
      detail: warning,
    });
  });

  metricSheetWarnings.forEach((warning, index) => {
    items.push({
      id: `metric-sheet-warning-${index}`,
      label: 'Metric Sheet',
      status: 'warning',
      detail: warning,
    });
  });

  if (!items.length) {
    items.push({
      id: 'data-cache',
      label: 'Data cache',
      status: 'success',
      detail: 'No active warnings for the current portfolio scope.',
    });
  }

  return items;
}

export default function DashboardPortfolioHealth({ items }) {
  return (
    <AppCard
      title="Portfolio Health"
      subtitle="Review queue"
      compact
      className="dashboard-health-card"
    >
      <ul
        className="dashboard-health-list"
        aria-label="Portfolio health checks"
        data-item-count={items.length}
      >
        {items.map((item) => (
          <li key={item.id} className="dashboard-health-list__item">
            <div className="dashboard-health-list__header">
              <strong className="dashboard-health-list__label">{item.label}</strong>
              <StatusBadge
                status={item.status}
                label={STATUS_LABELS[item.status] || item.status}
                className="dashboard-health-list__badge"
              />
            </div>
            <p className="dashboard-health-list__detail">{item.detail}</p>
          </li>
        ))}
      </ul>
    </AppCard>
  );
}
