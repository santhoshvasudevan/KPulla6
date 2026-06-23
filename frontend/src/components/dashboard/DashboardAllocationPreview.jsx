import { AppCard } from '../ui';
import { formatCurrency } from '../../utils/formatters';
import { getSeriesColor } from '../charts/chartTheme';

export default function DashboardAllocationPreview({ buckets = [], currency = 'EUR', total = 0 }) {
  if (!buckets.length || total <= 0) {
    return (
      <AppCard
        title="Allocation Preview"
        subtitle="Current mix"
        compact
        className="dashboard-allocation-card"
      >
        <p className="dashboard-allocation-empty">
          Allocation preview unavailable until backend allocation buckets are present.
        </p>
      </AppCard>
    );
  }

  return (
    <AppCard
      title="Allocation Preview"
      subtitle="Current mix"
      compact
      className="dashboard-allocation-card"
    >
      <div className="dashboard-allocation-bar" aria-hidden="true">
        {buckets.map((bucket, index) => (
          <span
            key={bucket.label}
            className="dashboard-allocation-bar__segment"
            style={{
              width: `${(Number(bucket.value) / total) * 100}%`,
              backgroundColor: getSeriesColor(index),
            }}
          />
        ))}
      </div>
      <dl className="dashboard-allocation-rows">
        {buckets.map((bucket) => (
          <div key={bucket.label} className="dashboard-allocation-row">
            <dt>{bucket.label}</dt>
            <dd>
              <span className="dashboard-allocation-row__value">
                {formatCurrency(Number(bucket.value), currency)}
              </span>
              <span className="dashboard-allocation-row__weight">
                {((Number(bucket.value) / total) * 100).toFixed(1)}%
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </AppCard>
  );
}
