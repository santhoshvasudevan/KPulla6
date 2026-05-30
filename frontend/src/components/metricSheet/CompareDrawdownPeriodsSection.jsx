import MetricSheetDrawdownPeriodsTable from './MetricSheetDrawdownPeriodsTable';

/**
 * Per-subject worst drawdown tables for Compare page.
 */
export default function CompareDrawdownPeriodsSection({ subjects = [], className = '' }) {
  if (!subjects.length) return null;

  return (
    <section
      className={['compare-metric-sheet-extras', className].filter(Boolean).join(' ')}
      aria-label="Compare worst drawdowns"
    >
      <h2 className="compare-page__metrics-title">Worst drawdowns</h2>
      <div className="compare-drawdown-periods__grid">
        {subjects.map((subj) => (
          <div key={subj.id} className="compare-drawdown-periods__subject">
            <h3 className="compare-drawdown-periods__subject-title">
              {subj.name || subj.asset_symbol || subj.id}
            </h3>
            <MetricSheetDrawdownPeriodsTable
              drawdownPeriods={subj.drawdown_periods}
              hideHeading
              className="metric-sheet__drawdown-periods--embedded"
            />
          </div>
        ))}
      </div>
    </section>
  );
}
