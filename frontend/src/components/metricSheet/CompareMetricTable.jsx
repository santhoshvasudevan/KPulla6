import {
  formatMetricPercentFraction,
  formatMetricRatio,
  METRIC_EM_DASH,
} from '../../utils/metricFormatters';
import { METRIC_SHEET_XIRR_FULL_SCOPE_NOTE } from './metricSheetCopy';

function cellValue(value, format) {
  if (format === 'percent') {
    return formatMetricPercentFraction(value, { showSign: true });
  }
  if (format === 'ratio') {
    return formatMetricRatio(value);
  }
  return METRIC_EM_DASH;
}

function CompareMetricRow({ label, subjects, getValue, format = 'percent', helper }) {
  return (
    <tr>
      <th scope="row">
        {label}
        {helper ? <span className="compare-metric-table__helper">{helper}</span> : null}
      </th>
      {subjects.map((subj) => (
        <td key={subj.id}>{cellValue(getValue(subj), format)}</td>
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
          getValue={(s) => s.metrics?.return?.cumulative_return}
        />
        <CompareMetricRow
          label="CAGR"
          subjects={subjects}
          getValue={(s) => s.metrics?.return?.cagr}
        />
        <CompareMetricRow
          label="TWROR"
          subjects={subjects}
          getValue={(s) => s.metrics?.return?.twror}
        />
        <CompareMetricRow
          label="XIRR"
          subjects={subjects}
          getValue={(s) => s.metrics?.return?.xirr}
        />
      </CompareMetricGroup>
      {showXirrScopeNote ? (
        <p className="metric-sheet__note">{METRIC_SHEET_XIRR_FULL_SCOPE_NOTE}</p>
      ) : null}

      <CompareMetricGroup title="Risk">
        <CompareMetricRow
          label="Volatility"
          subjects={subjects}
          getValue={(s) => s.metrics?.risk?.volatility_annualized}
        />
        <CompareMetricRow
          label="Sharpe"
          subjects={subjects}
          getValue={(s) => s.metrics?.risk?.sharpe_ratio}
          format="ratio"
        />
        <CompareMetricRow
          label="Sortino"
          subjects={subjects}
          getValue={(s) => s.metrics?.risk?.sortino_ratio}
          format="ratio"
        />
        <CompareMetricRow
          label="Max Drawdown"
          subjects={subjects}
          getValue={(s) => s.metrics?.drawdown?.max_drawdown}
        />
        <CompareMetricRow
          label="Calmar"
          subjects={subjects}
          getValue={(s) => s.metrics?.drawdown?.calmar_ratio}
          format="ratio"
        />
      </CompareMetricGroup>

      {showBenchmark ? (
        <CompareMetricGroup title="Benchmark">
          <CompareMetricRow
            label="Beta"
            subjects={subjects}
            getValue={(s) => s.benchmark?.metrics?.beta}
            format="ratio"
          />
          <CompareMetricRow
            label="Alpha"
            subjects={subjects}
            getValue={(s) => s.benchmark?.metrics?.alpha}
          />
          <CompareMetricRow
            label="Correlation"
            subjects={subjects}
            getValue={(s) => s.benchmark?.metrics?.correlation}
            format="ratio"
          />
          <CompareMetricRow
            label="Information Ratio"
            subjects={subjects}
            getValue={(s) => s.benchmark?.metrics?.information_ratio}
            format="ratio"
          />
          <CompareMetricRow
            label="Tracking Error"
            subjects={subjects}
            getValue={(s) => s.benchmark?.metrics?.tracking_error}
          />
        </CompareMetricGroup>
      ) : null}
    </div>
  );
}
