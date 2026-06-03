import {
  formatMetricPercentFraction,
  METRIC_EM_DASH,
} from '../../utils/metricFormatters';
import MetricSheetMonthlyReturnsGrid from './MetricSheetMonthlyReturnsGrid';
import MetricSheetYearlyReturnChart from './MetricSheetYearlyReturnChart';
import './metricSheet.css';

function YearlyReturnsSubTable({ rows }) {
  if (!rows?.length) {
    return null;
  }

  return (
    <div className="metric-sheet__table-group">
      <h4 className="metric-sheet__table-title">Yearly</h4>
      <div className="metric-sheet-table-scroll">
        <table className="metric-sheet__table metric-sheet__data-table">
          <thead>
            <tr>
              <th scope="col">Period</th>
              <th scope="col" className="metric-sheet__data-table__num">
                Return
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.period}>
                <th scope="row">{row.period}</th>
                <td className="metric-sheet__data-table__num">
                  {formatMetricPercentFraction(row.return, { showSign: true })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Monthly and yearly compounded returns from backend `periodic_returns`.
 * @param {object} [props.periodicReturns]
 * @param {boolean} [props.showMonthly=true]
 * @param {boolean} [props.showYearly=true]
 */
export default function MetricSheetPeriodicReturnsTable({
  periodicReturns,
  showMonthly = true,
  showYearly = true,
  className = '',
}) {
  if (!showMonthly && !showYearly) return null;

  const monthly = periodicReturns?.monthly ?? [];
  const yearly = periodicReturns?.yearly ?? [];
  const showYearlyFallbackTable = showYearly && monthly.length === 0 && yearly.length > 0;

  return (
    <div className={['metric-sheet__periodic-returns', className].filter(Boolean).join(' ')}>
      {showYearly ? <MetricSheetYearlyReturnChart yearly={yearly} /> : null}
      <h3 className="metric-sheet__section-heading">Periodic returns</h3>
      {showMonthly ? (
        <MetricSheetMonthlyReturnsGrid monthly={monthly} yearly={yearly} />
      ) : null}
      {showYearlyFallbackTable ? <YearlyReturnsSubTable rows={yearly} /> : null}
    </div>
  );
}

export function formatDrawdownStatus(recovered) {
  if (recovered === true) return 'Recovered';
  if (recovered === false) return 'Unrecovered';
  return METRIC_EM_DASH;
}
