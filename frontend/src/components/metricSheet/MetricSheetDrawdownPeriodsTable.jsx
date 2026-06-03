import {
  formatMetricPercentFraction,
  metricFractionTone,
  METRIC_EM_DASH,
} from '../../utils/metricFormatters';
import { formatDrawdownStatus } from './MetricSheetPeriodicReturnsTable';
import MetricSheetDrawdownChart from './MetricSheetDrawdownChart';

function formatRecoveryDays(value) {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return METRIC_EM_DASH;
  }
  const n = Math.round(Number(value));
  if (n === 1) return '1 day';
  return `${n} days`;
}

/**
 * Worst drawdown episodes from backend `drawdown_periods.worst`.
 */
export default function MetricSheetDrawdownPeriodsTable({
  drawdownPeriods,
  drawdownSeries,
  hideHeading = false,
  className = '',
}) {
  const rows = drawdownPeriods?.worst ?? [];

  return (
    <div className={['metric-sheet__drawdown-periods', className].filter(Boolean).join(' ')}>
      <MetricSheetDrawdownChart
        drawdownSeries={drawdownSeries}
        drawdownPeriods={drawdownPeriods}
      />
      {hideHeading ? null : (
        <h3 className="metric-sheet__section-heading">Worst drawdowns</h3>
      )}
      {!rows.length ? (
        <p className="metric-sheet__empty-inline">
          No drawdown period data available for this range.
        </p>
      ) : (
        <div className="metric-sheet-table-scroll">
          <table className="metric-sheet__table metric-sheet__data-table">
          <thead>
            <tr>
              <th scope="col">Peak date</th>
              <th scope="col">Trough date</th>
              <th scope="col">Recovery date</th>
              <th scope="col" className="metric-sheet__data-table__num">
                Drawdown
              </th>
              <th scope="col" className="metric-sheet__data-table__num">
                Days to recovery
              </th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const tone = metricFractionTone(row.drawdown);
              const toneClass =
                tone !== 'neutral' ? `metric-sheet__value--${tone}` : '';
              const rowKey = `${row.start_date}-${row.trough_date}-${row.rank ?? index}`;
              return (
                <tr key={rowKey}>
                  <th scope="row">{row.start_date || METRIC_EM_DASH}</th>
                  <td>{row.trough_date || METRIC_EM_DASH}</td>
                  <td>{row.recovery_date || METRIC_EM_DASH}</td>
                  <td className={`metric-sheet__data-table__num ${toneClass}`.trim()}>
                    {formatMetricPercentFraction(row.drawdown, { showSign: true })}
                  </td>
                  <td className="metric-sheet__data-table__num">
                    {formatRecoveryDays(row.days_to_recovery)}
                  </td>
                  <td>{formatDrawdownStatus(row.recovered)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
      )}
    </div>
  );
}
