import {
  formatMetricPercentFraction,
  METRIC_EM_DASH,
} from '../../utils/metricFormatters';
import './metricSheet.css';

/**
 * Yearly periodic returns side-by-side for Compare subjects (monthly deferred).
 */
export default function ComparePeriodicReturnsSection({ subjects = [], className = '' }) {
  if (!subjects.length) return null;

  const periodSet = new Set();
  for (const subj of subjects) {
    for (const row of subj.periodic_returns?.yearly ?? []) {
      if (row?.period) periodSet.add(row.period);
    }
  }
  const periods = [...periodSet].sort();

  const headers = subjects.map((s) => s.name || s.asset_symbol || s.id);

  return (
    <section
      className={['compare-metric-sheet-extras', className].filter(Boolean).join(' ')}
      aria-label="Compare periodic returns"
    >
      <h2 className="compare-page__metrics-title">Periodic returns</h2>
      <h3 className="metric-sheet__section-heading">Yearly</h3>
      {!periods.length ? (
        <p className="metric-sheet__empty-inline">
          No yearly return data available for this comparison.
        </p>
      ) : (
        <div className="metric-sheet-table-scroll">
          <table className="metric-sheet__table metric-sheet__data-table compare-periodic-table">
          <thead>
            <tr>
              <th scope="col">Period</th>
              {headers.map((label) => (
                <th key={label} scope="col" className="metric-sheet__data-table__num">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map((period) => (
              <tr key={period}>
                <th scope="row">{period}</th>
                {subjects.map((subj) => {
                  const row = (subj.periodic_returns?.yearly ?? []).find(
                    (r) => r.period === period
                  );
                  const label = subj.name || subj.asset_symbol || subj.id;
                  return (
                    <td
                      key={`${subj.id}-${period}`}
                      className="metric-sheet__data-table__num"
                    >
                      {row
                        ? formatMetricPercentFraction(row.return, { showSign: true })
                        : METRIC_EM_DASH}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
    </section>
  );
}
