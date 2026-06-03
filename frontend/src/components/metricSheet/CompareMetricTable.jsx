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
import { METRIC_SHEET_XIRR_FULL_SCOPE_NOTE } from './metricSheetCopy';

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
  const highlightStates = metricKey
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
    (s) => s.metrics?.return?.xirr_scope === 'full_scope'
  );

  return (
    <div className={['compare-metric-table-wrap', 'metric-sheet-table-scroll', className].filter(Boolean).join(' ')}>
      <p className="compare-metric-table__highlight-note">{COMPARE_METRIC_HIGHLIGHT_NOTE}</p>
      <table className="compare-metric-table compare-metric-table--header">
        <thead>
          <tr>
            <th scope="col">Metric</th>
            {headers.map((label) => (
              <th key={label} scope="col">
                {label}
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
        <CompareMetricRow
          label="TWROR"
          subjects={subjects}
          metricKey="twror"
          getValue={(s) => s.metrics?.return?.twror}
        />
        <CompareMetricRow
          label="XIRR"
          subjects={subjects}
          metricKey="xirr"
          getValue={(s) => s.metrics?.return?.xirr}
        />
      </CompareMetricGroup>
      {showXirrScopeNote ? (
        <p className="metric-sheet__note">{METRIC_SHEET_XIRR_FULL_SCOPE_NOTE}</p>
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
