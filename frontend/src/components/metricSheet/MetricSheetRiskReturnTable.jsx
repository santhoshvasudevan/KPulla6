import {
  formatMetricDays,
  formatMetricPercentFraction,
  formatMetricRatio,
  metricFractionTone,
} from '../../utils/metricFormatters';

function MetricRow({ label, value, format = 'percent', toneFromValue = false }) {
  let display = value;
  if (format === 'percent') {
    display = formatMetricPercentFraction(value, { showSign: true });
  } else if (format === 'ratio') {
    display = formatMetricRatio(value);
  } else if (format === 'days') {
    display = formatMetricDays(value);
  }

  const toneClass =
    toneFromValue && metricFractionTone(value) !== 'neutral'
      ? `metric-sheet__value--${metricFractionTone(value)}`
      : '';

  return (
    <tr>
      <th scope="row">{label}</th>
      <td className={toneClass}>{display}</td>
    </tr>
  );
}

function MetricTableGroup({ title, children }) {
  return (
    <div className="metric-sheet__table-group">
      <h4 className="metric-sheet__table-title">{title}</h4>
      <table className="metric-sheet__table">
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export default function MetricSheetRiskReturnTable({ metrics, className = '' }) {
  if (!metrics) return null;

  const risk = metrics.risk ?? {};
  const drawdown = metrics.drawdown ?? {};
  const periods = metrics.periods ?? {};

  return (
    <div className={className}>
      <MetricTableGroup title="Risk">
        <MetricRow label="Volatility (annualized)" value={risk.volatility_annualized} />
        <MetricRow label="Downside Deviation" value={risk.downside_deviation} />
        <MetricRow label="Sharpe Ratio" value={risk.sharpe_ratio} format="ratio" />
        <MetricRow label="Sortino Ratio" value={risk.sortino_ratio} format="ratio" />
      </MetricTableGroup>

      <MetricTableGroup title="Drawdown">
        <MetricRow
          label="Max Drawdown"
          value={drawdown.max_drawdown}
          toneFromValue
        />
        <MetricRow
          label="Longest Drawdown"
          value={drawdown.longest_drawdown_days}
          format="days"
        />
        <MetricRow label="Calmar Ratio" value={drawdown.calmar_ratio} format="ratio" />
      </MetricTableGroup>

      <MetricTableGroup title="Period">
        <MetricRow label="Best Day" value={periods.best_day} toneFromValue />
        <MetricRow label="Worst Day" value={periods.worst_day} toneFromValue />
        <MetricRow label="Win Rate" value={periods.win_rate} />
        <MetricRow label="Average Daily Return" value={periods.average_daily_return} toneFromValue />
      </MetricTableGroup>
    </div>
  );
}
