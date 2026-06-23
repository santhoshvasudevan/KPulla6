import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchBenchmarkIndices,
  fetchHoldings,
  getCompareMetricSheet,
} from '../api';
import { usePortfolio } from '../portfolioContext';
import { buildCompareAssetOptions } from '../utils/compareHoldings';
import {
  compareBenchmarkLabel,
  compareChartLegendItems,
  compareOptionLabel,
  compareSubjectSummaryKpis,
} from '../utils/compareDisplay';
import {
  PageHeader,
  AppCard,
  SectionHeader,
  SegmentedControl,
  KpiCard,
  PercentValue,
  LoadingState,
  ErrorState,
  EmptyState,
  WarningBanner,
} from '../components/ui';
import { ChartFrame, ChartControls, ChartLegend } from '../components/charts';
import {
  MetricSheetWarnings,
  CompareNormalizedChart,
  CompareMetricTable,
  ComparePeriodicReturnsSection,
  CompareDrawdownPeriodsSection,
} from '../components/metricSheet';
import { formatCompareRangeContext } from '../components/metricSheet/metricSheetCopy';
import './Compare.css';
import '../components/metricSheet/compareMetricSheet.css';

const RANGE_OPTIONS = ['7D', '30D', 'YTD', '1Y', '3Y', '5Y', 'ALL'];

const COMPARE_SECTION_NAV = [
  { href: '#compare-setup', label: 'Setup' },
  { href: '#compare-chart', label: 'Chart' },
  { href: '#compare-metrics', label: 'Metrics' },
  { href: '#compare-periods', label: 'Periods' },
  { href: '#compare-drawdowns', label: 'Drawdowns' },
];

function CompareAssetOptions({ options, excludeSymbol, placeholder }) {
  const active = options.filter((o) => o.active);
  const closed = options.filter((o) => !o.active);

  return (
    <>
      <option value="">{placeholder}</option>
      {active.length > 0 ? (
        <optgroup label="Open holdings">
          {active.map((o) => (
            <option key={o.symbol} value={o.symbol} disabled={o.symbol === excludeSymbol}>
              {o.label}
            </option>
          ))}
        </optgroup>
      ) : null}
      {closed.length > 0 ? (
        <optgroup label="Closed holdings">
          {closed.map((o) => (
            <option key={o.symbol} value={o.symbol} disabled={o.symbol === excludeSymbol}>
              {o.label}
            </option>
          ))}
        </optgroup>
      ) : null}
    </>
  );
}

function isMultiFolioCompareError(message) {
  const text = String(message || '').toLowerCase();
  return text.includes('folio_number') || text.includes('multiple folios');
}

function buildCompareSubjectsParam(assetA, assetB) {
  return `asset:${assetA},asset:${assetB}`;
}

function plTone(val) {
  if (val == null || Number.isNaN(Number(val))) return 'neutral';
  const n = Number(val);
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
  return 'neutral';
}

function kpiVariantFromTone(tone) {
  if (tone === 'positive') return 'gain';
  if (tone === 'negative') return 'loss';
  return undefined;
}

export default function Compare() {
  const { apiQuery, selectedPortfolioName, selectedDisplayCurrency, settingsLoaded } =
    usePortfolio();

  const [holdings, setHoldings] = useState([]);
  const [holdingsLoading, setHoldingsLoading] = useState(true);
  const [holdingsError, setHoldingsError] = useState('');

  const [assetA, setAssetA] = useState('');
  const [assetB, setAssetB] = useState('');
  const [timeRange, setTimeRange] = useState('1Y');
  const [selectedBenchmark, setSelectedBenchmark] = useState('');
  const [benchmarkOptions, setBenchmarkOptions] = useState([]);

  const [compareData, setCompareData] = useState(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState('');

  const compareRequestIdRef = useRef(0);

  const assetOptions = useMemo(() => buildCompareAssetOptions(holdings), [holdings]);
  const sameAssetSelected = assetA && assetB && assetA === assetB;
  const canCompare =
    settingsLoaded &&
    apiQuery &&
    assetA &&
    assetB &&
    !sameAssetSelected;

  const loadHoldings = useCallback(() => {
    if (!settingsLoaded || !apiQuery) return;
    setHoldingsLoading(true);
    setHoldingsError('');
    fetchHoldings(apiQuery)
      .then((data) => {
        setHoldings(data.holdings || []);
        setHoldingsLoading(false);
      })
      .catch((err) => {
        setHoldingsError(err.message || 'Failed to load holdings');
        setHoldingsLoading(false);
      });
  }, [settingsLoaded, apiQuery]);

  useEffect(() => {
    loadHoldings();
  }, [loadHoldings]);

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
    if (!canCompare) {
      setCompareData(null);
      setCompareError('');
      setCompareLoading(false);
      return;
    }

    const requestId = ++compareRequestIdRef.current;
    setCompareLoading(true);
    setCompareError('');

    const params = {
      ...apiQuery,
      range: timeRange,
      subjects: buildCompareSubjectsParam(assetA, assetB),
    };
    if (selectedBenchmark) {
      params.benchmark = selectedBenchmark;
    }

    getCompareMetricSheet(params)
      .then((data) => {
        if (requestId !== compareRequestIdRef.current) return;
        setCompareData(data);
        setCompareLoading(false);
      })
      .catch((err) => {
        if (requestId !== compareRequestIdRef.current) return;
        setCompareError(err.message || 'Failed to load comparison');
        setCompareData(null);
        setCompareLoading(false);
      });
  }, [canCompare, apiQuery, assetA, assetB, timeRange, selectedBenchmark]);

  const shortChartRange = timeRange === '7D' || timeRange === '30D';
  const rangeOptions = RANGE_OPTIONS.map((r) => ({ value: r, label: r }));

  const headerSubtitle = [
    selectedPortfolioName || 'All Portfolios',
    (selectedDisplayCurrency || 'EUR').toUpperCase(),
    'Side-by-side quantitative comparison',
  ].join(' · ');

  const rangeContextNote = useMemo(
    () => formatCompareRangeContext(timeRange, compareData),
    [timeRange, compareData]
  );

  const subjectKpis = useMemo(
    () => compareSubjectSummaryKpis(compareData?.subjects),
    [compareData]
  );

  const chartLegendItems = useMemo(
    () => compareChartLegendItems(compareData?.subjects, compareData?.normalized_series),
    [compareData]
  );

  const assetALabel = compareOptionLabel(assetOptions, assetA);
  const assetBLabel = compareOptionLabel(assetOptions, assetB);
  const benchmarkLabel = compareBenchmarkLabel(benchmarkOptions, selectedBenchmark);

  const mfFolioMessage =
    'This mutual fund has multiple folios. Compare by folio is not available yet.';

  if (!settingsLoaded || holdingsLoading) {
    return (
      <LoadingState
        message={
          !settingsLoaded ? 'Loading display settings…' : 'Loading holdings for comparison…'
        }
      />
    );
  }

  if (holdingsError) {
    return (
      <ErrorState
        title="Unable to load holdings"
        message={holdingsError}
        onRetry={loadHoldings}
      />
    );
  }

  if (assetOptions.length < 2) {
    return (
      <div className="compare-page">
        <PageHeader title="Compare Assets" subtitle={headerSubtitle} />
        <EmptyState
          title="Need at least two assets"
          description="Add holdings in this portfolio view before comparing assets side by side."
        />
      </div>
    );
  }

  return (
    <div className="compare-page">
      <PageHeader
        title="Compare Assets"
        subtitle={headerSubtitle}
        eyebrow="Quantitative Statistics"
      />

      <div id="compare-setup">
        <AppCard
          className="compare-page__setup"
          title="Comparison setup"
          subtitle="Select two assets, time range, and optional benchmark"
        >
          <div className="compare-page__pickers">
            <div className="compare-page__field">
              <label className="compare-page__label" htmlFor="compare-asset-a">
                Asset A
              </label>
              <select
                id="compare-asset-a"
                aria-label="compare-asset-a"
                className="compare-page__select"
                value={assetA}
                onChange={(e) => setAssetA(e.target.value)}
              >
                <CompareAssetOptions
                  options={assetOptions}
                  excludeSymbol={assetB}
                  placeholder="Select asset…"
                />
              </select>
            </div>
            <div className="compare-page__field">
              <label className="compare-page__label" htmlFor="compare-asset-b">
                Asset B
              </label>
              <select
                id="compare-asset-b"
                aria-label="compare-asset-b"
                className="compare-page__select"
                value={assetB}
                onChange={(e) => setAssetB(e.target.value)}
              >
                <CompareAssetOptions
                  options={assetOptions}
                  excludeSymbol={assetA}
                  placeholder="Select asset…"
                />
              </select>
            </div>
          </div>

          {assetA || assetB || selectedBenchmark ? (
            <div className="compare-page__chips" aria-label="Selected comparison subjects">
              {assetA ? (
                <span className="compare-page__chip compare-page__chip--a">Asset A: {assetALabel}</span>
              ) : null}
              {assetB ? (
                <span className="compare-page__chip compare-page__chip--b">Asset B: {assetBLabel}</span>
              ) : null}
              {selectedBenchmark ? (
                <span className="compare-page__chip compare-page__chip--benchmark">
                  Benchmark: {benchmarkLabel}
                </span>
              ) : null}
            </div>
          ) : null}

          <ChartControls className="compare-page__controls" ariaLabel="Comparison controls">
            <div className="compare-page__control-group">
              <span className="compare-page__label">Time range</span>
              <SegmentedControl
                ariaLabel="compare-time-range"
                options={rangeOptions}
                value={timeRange}
                onChange={setTimeRange}
              />
            </div>
            <div className="compare-page__field compare-page__field--benchmark">
              <label className="compare-page__label" htmlFor="compare-benchmark">
                Benchmark
              </label>
              <select
                id="compare-benchmark"
                aria-label="compare-benchmark"
                className="compare-page__benchmark-select"
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
          </ChartControls>
        </AppCard>
      </div>

      {sameAssetSelected ? (
        <WarningBanner
          severity="warning"
          message="Select two different assets to compare."
        />
      ) : null}

      <nav className="compare-section-nav" aria-label="Compare section navigation">
        {COMPARE_SECTION_NAV.map((item) => (
          <a key={item.href} className="compare-section-nav__link" href={item.href}>
            {item.label}
          </a>
        ))}
      </nav>

      {!assetA || !assetB ? (
        <EmptyState
          title="Choose two assets"
          description="Pick Asset A and Asset B to load side-by-side Metric Sheet comparison."
        />
      ) : compareLoading ? (
        <LoadingState message="Loading comparison…" variant="skeleton" />
      ) : compareError ? (
        <ErrorState
          title="Comparison unavailable"
          message={
            isMultiFolioCompareError(compareError) ? mfFolioMessage : compareError
          }
        />
      ) : compareData ? (
        <>
          <MetricSheetWarnings warnings={compareData.warnings} />
          {rangeContextNote ? (
            <p className="compare-page__alignment" role="note">
              {rangeContextNote}
            </p>
          ) : null}

          {subjectKpis.length > 0 ? (
            <div
              className="compare-page__kpi-strip"
              id="compare-overview"
              aria-label="Comparison summary"
            >
              {subjectKpis.map((kpi) => (
                <KpiCard
                  key={kpi.id}
                  label={kpi.label}
                  size="compact"
                  helperText="Cumulative return"
                  variant={kpiVariantFromTone(plTone(kpi.cumulativeReturn))}
                  value={
                    <PercentValue
                      value={kpi.cumulativeReturn}
                      tone={plTone(kpi.cumulativeReturn)}
                      showSign
                    />
                  }
                />
              ))}
              {compareData.common_point_count != null ? (
                <KpiCard
                  label="Common points"
                  size="compact"
                  helperText="Overlapping dates"
                  value={String(compareData.common_point_count)}
                />
              ) : null}
            </div>
          ) : null}

          <div id="compare-chart">
            <ChartFrame
              title="Normalized Cumulative Return"
              subtitle="First common date = 0%"
              density="analysis"
              className="compare-page__chart"
              legend={
                chartLegendItems.length ? <ChartLegend items={chartLegendItems} /> : null
              }
            >
              <CompareNormalizedChart
                normalizedSeries={compareData.normalized_series}
                subjects={compareData.subjects}
                shortRange={shortChartRange}
                hideLegend
              />
            </ChartFrame>
          </div>

          <div id="compare-metrics">
            <AppCard className="compare-page__metrics">
              <SectionHeader
                title="Metric Sheet comparison"
                headingLevel={2}
                className="compare-page__metrics-header"
              />
              <CompareMetricTable
                subjects={compareData.subjects}
                showBenchmark={Boolean(selectedBenchmark)}
              />
            </AppCard>
          </div>

          <div id="compare-periods">
            <ComparePeriodicReturnsSection subjects={compareData.subjects} />
          </div>

          <div id="compare-drawdowns">
            <CompareDrawdownPeriodsSection subjects={compareData.subjects} />
          </div>

          {(compareData.subjects || []).some((s) => s.warnings?.length) ? (
            <div className="compare-page__subject-warnings">
              {(compareData.subjects || []).map((subj) =>
                subj.warnings?.length ? (
                  <div key={subj.id}>
                    <p className="compare-page__subject-warning-title">
                      {subj.name || subj.asset_symbol}
                    </p>
                    <MetricSheetWarnings warnings={subj.warnings} />
                  </div>
                ) : null
              )}
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
