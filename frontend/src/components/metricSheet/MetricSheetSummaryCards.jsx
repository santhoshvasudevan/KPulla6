import { MetricCard } from '../ui';
import {
  formatMetricPercentFraction,
  metricFractionTone,
} from '../../utils/metricFormatters';
import { METRIC_SHEET_XIRR_FULL_SCOPE_NOTE } from './metricSheetCopy';

export default function MetricSheetSummaryCards({ metrics, className = '', showXirr = true, performanceBasis }) {
  const returns = metrics?.return ?? {};

  const cards = [
    { label: performanceBasis === 'nav' ? 'Cumulative NAV Return' : 'Cumulative Return', value: returns.cumulative_return },
    { label: 'CAGR', value: returns.cagr },
    ...(performanceBasis === 'nav' ? [] : [{ label: 'TWROR', value: returns.twror }]),
    ...(showXirr ? [{ label: 'XIRR', value: returns.xirr }] : []),
  ];

  const xirrScopeNote =
    returns.xirr_scope === 'full_scope' ? METRIC_SHEET_XIRR_FULL_SCOPE_NOTE : null;

  return (
    <div className={className}>
      <div className="metric-sheet__cards">
        {cards.map(({ label, value }) => (
          <MetricCard
            key={label}
            label={label}
            value={formatMetricPercentFraction(value, { showSign: true })}
            tone={metricFractionTone(value)}
            helperText={label === 'XIRR' ? xirrScopeNote : undefined}
          />
        ))}
      </div>
    </div>
  );
}
