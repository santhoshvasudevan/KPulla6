import { useEffect, useRef, useState } from 'react';
import { fetchBenchmarkIndices, getAssetMetricSheet } from '../../api';
import { LoadingState, ErrorState, SegmentedControl } from '../ui';
import MetricSheetSection from './MetricSheetSection';
import MetricSheetSummaryCards from './MetricSheetSummaryCards';
import MetricSheetRiskReturnTable from './MetricSheetRiskReturnTable';
import MetricSheetBenchmarkTable from './MetricSheetBenchmarkTable';
import MetricSheetWarnings from './MetricSheetWarnings';
import MetricSheetPeriodicReturnsTable from './MetricSheetPeriodicReturnsTable';
import MetricSheetDrawdownPeriodsTable from './MetricSheetDrawdownPeriodsTable';
import './assetDetailMetricSheet.css';

const METRIC_SHEET_RANGE_OPTIONS = ['7D', '30D', 'YTD', '1Y', '3Y', '5Y', 'ALL'];

function isFolioRequiredError(message) {
  const text = String(message || '').toLowerCase();
  return text.includes('folio_number') || text.includes('multiple folios');
}

export default function AssetDetailMetricSheet({
  assetSymbol,
  apiQuery,
  folioNumber,
  settingsLoaded,
}) {
  const [metricSheetRange, setMetricSheetRange] = useState('1Y');
  const [selectedBenchmark, setSelectedBenchmark] = useState('');
  const [benchmarkOptions, setBenchmarkOptions] = useState([]);
  const [metricSheetData, setMetricSheetData] = useState(null);
  const [metricSheetLoading, setMetricSheetLoading] = useState(true);
  const [metricSheetError, setMetricSheetError] = useState('');
  const requestIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    fetchBenchmarkIndices()
      .then((rows) => {
        if (!cancelled) setBenchmarkOptions(Array.isArray(rows) ? rows : []);
      })
      .catch(() => {
        if (!cancelled) setBenchmarkOptions([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!settingsLoaded || !apiQuery || !assetSymbol) return;

    const requestId = ++requestIdRef.current;
    setMetricSheetLoading(true);
    setMetricSheetError('');

    const params = {
      ...apiQuery,
      range: metricSheetRange,
    };
    if (selectedBenchmark) {
      params.benchmark = selectedBenchmark;
    }
    if (folioNumber) {
      params.folio_number = folioNumber;
    }

    getAssetMetricSheet(assetSymbol, params)
      .then((payload) => {
        if (requestId !== requestIdRef.current) return;
        setMetricSheetData(payload);
        setMetricSheetLoading(false);
      })
      .catch((err) => {
        if (requestId !== requestIdRef.current) return;
        setMetricSheetError(err.message || 'Failed to load Metric Sheet');
        setMetricSheetData(null);
        setMetricSheetLoading(false);
      });
  }, [
    settingsLoaded,
    apiQuery,
    assetSymbol,
    folioNumber,
    metricSheetRange,
    selectedBenchmark,
  ]);

  const rangeOptions = METRIC_SHEET_RANGE_OPTIONS.map((r) => ({ value: r, label: r }));

  const subtitle = metricSheetData?.range
    ? `Quantitative Statistics · ${metricSheetData.range.code} (${metricSheetData.range.start} – ${metricSheetData.range.end})`
    : `Quantitative Statistics · ${metricSheetRange}`;

  const folioMessage = "Select a specific folio to view this asset's Metric Sheet.";

  return (
    <MetricSheetSection
      className="asset-detail-metric-sheet"
      subtitle={subtitle}
      actions={
        <div className="asset-detail-metric-sheet__toolbar">
          <SegmentedControl
            ariaLabel="asset-metric-sheet-range"
            options={rangeOptions}
            value={metricSheetRange}
            onChange={setMetricSheetRange}
          />
          <select
            aria-label="asset-metric-sheet-benchmark"
            className="metric-sheet__benchmark-select asset-detail-metric-sheet__benchmark-select"
            value={selectedBenchmark}
            onChange={(e) => setSelectedBenchmark(e.target.value)}
          >
            <option value="">No benchmark</option>
            {benchmarkOptions.map((b) => (
              <option key={b.symbol} value={b.symbol}>
                {b.name || b.display_name || b.symbol}
              </option>
            ))}
          </select>
        </div>
      }
    >
      {metricSheetLoading ? (
        <LoadingState message="Loading Metric Sheet…" variant="skeleton" />
      ) : metricSheetError ? (
        <ErrorState
          title="Metric Sheet unavailable"
          message={isFolioRequiredError(metricSheetError) ? folioMessage : metricSheetError}
        />
      ) : metricSheetData ? (
        <>
          <MetricSheetWarnings warnings={metricSheetData.warnings} />
          <MetricSheetSummaryCards metrics={metricSheetData.metrics} />
          <MetricSheetRiskReturnTable metrics={metricSheetData.metrics} />
          {selectedBenchmark && metricSheetData.benchmark ? (
            <MetricSheetBenchmarkTable benchmark={metricSheetData.benchmark} />
          ) : null}
          <MetricSheetPeriodicReturnsTable
            periodicReturns={metricSheetData.periodic_returns}
          />
          <MetricSheetDrawdownPeriodsTable
            drawdownPeriods={metricSheetData.drawdown_periods}
          />
        </>
      ) : null}
    </MetricSheetSection>
  );
}
