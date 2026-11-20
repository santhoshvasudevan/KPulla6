import {
  formatMetricPercentFraction,
  formatMetricRatio,
  METRIC_EM_DASH,
} from '../../utils/metricFormatters';
import {
  COMPARE_HIGHLIGHT,
  COMPARE_HIGHLIGHT_LABELS,
  getCompareHighlightStates,
} from './compareMetricRanking';
import { METRIC_SHEET_XIRR_FULL_SCOPE_NOTE, personalXirrHelperText } from './metricSheetCopy';
import MetricSheetWarnings from './MetricSheetWarnings';
import MetricSheetNavCoverage from './MetricSheetNavCoverage';

export const COMPARE_METRIC_HIGHLIGHT_NOTE =
  'Subtle highlights indicate the stronger value where metric direction is clear.';

function cellValue(value, format) {
  if (format === 'percent') {
    return formatMetricPercentFraction(value, { showSign: true });
  }
  if (format === 'ratio') {
    return formatMetricRatio(value);
  }
  return METRIC_EM_DASH;
}

function highlightClass(state) {
  if (
    state === COMPARE_HIGHLIGHT.BETTER ||
    state === COMPARE_HIGHLIGHT.WORSE ||
    state === COMPARE_HIGHLIGHT.TIE
  ) {
    return `compare-metric-value--${state}`;
  }
  return '';
}

function CompareMetricCell({ value, format, highlightState }) {
  const label = COMPARE_HIGHLIGHT_LABELS[highlightState];
  const className = highlightClass(highlightState);

  return (
    <td className={className || undefined} title={label || undefined}>
      {label ? <span className="compare-metric-value__sr-only">{label}</span> : null}
      {cellValue(value, format)}
    </td>
  );
}

function CompareMetricRow({ label, subjects, getValue, format = 'percent', helper, metricKey }) {
  const values = subjects.map((subj) => getValue(subj));
  const mixedBases = new Set(subjects.map((s) => s.performance_basis).filter(Boolean)).size > 1;
  const mixedCurrencies = new Set(subjects.map((s) => s.currency).filter(Boolean)).size > 1;
  const highlightStates = metricKey && !mixedBases && !mixedCurrencies
    ? getCompareHighlightStates(metricKey, values)
    : [COMPARE_HIGHLIGHT.NEUTRAL, COMPARE_HIGHLIGHT.NEUTRAL];

  return (
    <tr>
      <th scope="row">
        {label}
        {helper ? <span className="compare-metric-table__helper">{helper}</span> : null}
      </th>
      {subjects.map((subj, index) => (
        <CompareMetricCell
          key={subj.id}
          value={getValue(subj)}
          format={format}
          highlightState={highlightStates[index]}
        />
      ))}
    </tr>
  );
}

function CompareMetricGroup({ title, children }) {
  return (
    <div className="compare-metric-table__group">
      <h4 className="compare-metric-table__group-title">{title}</h4>
      <table className="compare-metric-table">
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export default function CompareMetricTable({ subjects = [], showBenchmark = false, className = '' }) {
  if (!subjects.length) return null;

  const headers = subjects.map((s) => s.name || s.asset_symbol || s.id);
  const showXirrScopeNote = subjects.some(
    (s) => s.performance_basis !== 'nav' && s.metrics?.return?.xirr_scope === 'full_scope'
  );
  const hasNav = subjects.some((s) => s.performance_basis === 'nav');

  return (
    <div className={['compare-metric-table-wrap', 'metric-sheet-table-scroll', className].filter(Boolean).join(' ')}>
      <p className="compare-metric-table__highlight-note">{COMPARE_METRIC_HIGHLIGHT_NOTE}</p>
      <table className="compare-metric-table compare-metric-table--header">
        <thead>
          <tr>
            <th scope="col">Metric</th>
            {headers.map((label, index) => (
              <th key={subjects[index].id} scope="col">
                {label}
                {subjects[index].performance_basis || subjects[index].currency ? (
                  <span className="compare-metric-table__helper">
                    {[
                      subjects[index].performance_basis === 'nav' ? 'NAV' :
                        ['cash_flow_adjusted', 'holding_cash_flow_adjusted'].includes(subjects[index].performance_basis) ? 'Cash-flow adjusted' : subjects[index].performance_basis,
                      subjects[index].currency,
                    ].filter(Boolean).join(' · ')}
                  </span>
                ) : null}
                {subjects[index].performance_basis === 'nav' ? (
                  <MetricSheetNavCoverage coverage={subjects[index].coverage} />
                ) : null}
              </th>
            ))}
          </tr>
        </thead>
      </table>

      <CompareMetricGroup title="Return">
        <CompareMetricRow
          label="Cumulative Return"
          subjects={subjects}
          metricKey="cumulative_return"
          getValue={(s) => s.metrics?.return?.cumulative_return}
        />
        <CompareMetricRow
          label="CAGR"
          subjects={subjects}
          metricKey="cagr"
          getValue={(s) => s.metrics?.return?.cagr}
        />
        {subjects.some((s) => s.performance_basis !== 'nav') && <CompareMetricRow
          label="TWROR"
          subjects={subjects}
          metricKey="twror"
          getValue={(s) => s.performance_basis === 'nav' ? null : s.metrics?.return?.twror}
        />}
        {subjects.some((s) => s.performance_basis !== 'nav') ? <CompareMetricRow
          label="XIRR"
          subjects={subjects}
          metricKey="xirr"
          getValue={(s) => s.performance_basis === 'nav' ? null : s.metrics?.return?.xirr}
        /> : null}
      </CompareMetricGroup>
      {showXirrScopeNote ? (
        <p className="metric-sheet__note">{METRIC_SHEET_XIRR_FULL_SCOPE_NOTE}</p>
      ) : null}

      {hasNav ? (
        <CompareMetricGroup title="Your Position">
          <tr>
            <th scope="row">Your Holding XIRR</th>
            {subjects.map((subject) => (
              <td key={subject.id}>
                {cellValue(subject.personal_metrics?.xirr, 'percent')}
                {subject.performance_basis === 'nav' ? (
                  <>
                    <span className="compare-metric-table__helper">{personalXirrHelperText(subject.personal_metrics?.status)}</span>
                    {subject.personal_metrics?.xirr_scope === 'full_scope' ? (
                      <span className="compare-metric-table__helper">Full-scope personal return</span>
                    ) : null}
                    <MetricSheetWarnings warnings={subject.personal_metrics?.warnings} />
                  </>
                ) : null}
              </td>
            ))}
          </tr>
        </CompareMetricGroup>
      ) : null}

      <CompareMetricGroup title="Risk">
        <CompareMetricRow
          label="Volatility (annualized)"
          subjects={subjects}
          metricKey="volatility_annualized"
          getValue={(s) => s.metrics?.risk?.volatility_annualized}
        />
        <CompareMetricRow
          label="Sharpe Ratio"
          subjects={subjects}
          metricKey="sharpe_ratio"
          getValue={(s) => s.metrics?.risk?.sharpe_ratio}
          format="ratio"
        />
        <CompareMetricRow
          label="Sortino Ratio"
          subjects={subjects}
          metricKey="sortino_ratio"
          getValue={(s) => s.metrics?.risk?.sortino_ratio}
          format="ratio"
        />
        <CompareMetricRow
          label="Max Drawdown"
          subjects={subjects}
          metricKey="max_drawdown"
          getValue={(s) => s.metrics?.drawdown?.max_drawdown}
        />
        <CompareMetricRow
          label="Calmar Ratio"
          subjects={subjects}
          metricKey="calmar_ratio"
          getValue={(s) => s.metrics?.drawdown?.calmar_ratio}
          format="ratio"
        />
      </CompareMetricGroup>

      {showBenchmark ? (
        <CompareMetricGroup title="Benchmark">
          <CompareMetricRow
            label="Beta"
            subjects={subjects}
            metricKey="beta"
            getValue={(s) => s.benchmark?.metrics?.beta}
            format="ratio"
          />
          <CompareMetricRow
            label="Alpha"
            subjects={subjects}
            metricKey="alpha"
            getValue={(s) => s.benchmark?.metrics?.alpha}
          />
          <CompareMetricRow
            label="Correlation"
            subjects={subjects}
            metricKey="correlation"
            getValue={(s) => s.benchmark?.metrics?.correlation}
            format="ratio"
          />
          <CompareMetricRow
            label="Information Ratio"
            subjects={subjects}
            metricKey="information_ratio"
            getValue={(s) => s.benchmark?.metrics?.information_ratio}
            format="ratio"
          />
          <CompareMetricRow
            label="Tracking Error"
            subjects={subjects}
            metricKey="tracking_error"
            getValue={(s) => s.benchmark?.metrics?.tracking_error}
          />
        </CompareMetricGroup>
      ) : null}
    </div>
  );
}
