import {
  formatMetricNumber,
  formatMetricPercentFraction,
  formatMetricRatio,
  METRIC_EM_DASH,
} from '../../utils/metricFormatters';

function BenchmarkRow({ label, value, format = 'ratio' }) {
  let display = METRIC_EM_DASH;
  if (value != null && value !== '' && !Number.isNaN(Number(value))) {
    if (format === 'percent') {
      display = formatMetricPercentFraction(value, { showSign: true });
    } else if (format === 'count') {
      display = formatMetricNumber(value);
    } else {
      display = formatMetricRatio(value);
    }
  }
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{display}</td>
    </tr>
  );
}

export default function MetricSheetBenchmarkTable({ benchmark, className = '' }) {
  if (!benchmark) return null;

  const { symbol, paired_count: pairedCount, metrics } = benchmark;
  const hasMetrics = metrics != null;

  return (
    <div className={className}>
      <p className="metric-sheet__benchmark-symbol">
        Benchmark: <strong>{symbol || METRIC_EM_DASH}</strong>
      </p>
      <table className="metric-sheet__table">
        <tbody>
          <BenchmarkRow label="Paired Count" value={pairedCount} format="count" />
          {hasMetrics ? (
            <>
              <BenchmarkRow label="Correlation" value={metrics.correlation} />
              <BenchmarkRow label="Beta" value={metrics.beta} />
              <BenchmarkRow label="Alpha" value={metrics.alpha} format="percent" />
              <BenchmarkRow label="Active Return" value={metrics.active_return} format="percent" />
              <BenchmarkRow label="Tracking Error" value={metrics.tracking_error} format="percent" />
              <BenchmarkRow label="Information Ratio" value={metrics.information_ratio} />
              <BenchmarkRow label="Treynor Ratio" value={metrics.treynor_ratio} />
            </>
          ) : (
            <tr>
              <th scope="row">Relative metrics</th>
              <td>{METRIC_EM_DASH}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
