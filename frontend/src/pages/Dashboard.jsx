import { useEffect, useState, useMemo, useRef } from 'react';
import {
  fetchDashboardSummary,
  fetchPortfolioPerformance,
  fetchBenchmarkIndices,
  getPortfolioMetricSheet,
} from '../api';
import { formatCurrency } from '../utils/formatters';
import { usePortfolio } from '../portfolioContext';
import {
  PageHeader,
  KpiCard,
  CurrencyValue,
  PercentValue,
  LoadingState,
  ErrorState,
  WarningBanner,
  SegmentedControl,
  EmptyState,
  SectionHeader,
} from '../components/ui';
import {
  MetricSheetSection,
  MetricSheetSummaryCards,
  MetricSheetRiskReturnTable,
  MetricSheetBenchmarkTable,
  MetricSheetWarnings,
  MetricSheetPeriodicReturnsTable,
  MetricSheetDrawdownPeriodsTable,
} from '../components/metricSheet';
import DashboardAllocationPreview from '../components/dashboard/DashboardAllocationPreview';
import DashboardPortfolioHealth, {
  buildPortfolioHealthItems,
} from '../components/dashboard/DashboardPortfolioHealth';
import {
  LineChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from 'recharts';
import {
  ChartFrame,
  ChartControls,
  ChartLegend,
  ChartEmptyState,
  getSeriesColorForRole,
  getSeriesStrokeProps,
  buildLegendItems,
  CHART_SERIES_ROLES,
  getComparisonBarFill,
  getChartGridProps,
  getChartAxisStroke,
  getChartAxisTick,
  getChartTooltipStyle,
  getChartLegendStyle,
  getChartBarInvestedColor,
  ChartRechartsTooltip,
  getChartMargin,
  getChartCrosshairCursorProps,
  getChartActiveDotProps,
  getChartMinTickGap,
  getChartHeight,
  getChartAnimationProps,
} from '../components/charts';
import {
  buildDashboardPerformanceChartConfig,
  findLatestValidChartReading,
} from '../components/dashboard/dashboardPerformanceChart';
import './Dashboard.css';

const DASHBOARD_SECTION_NAV = [
  { href: '#dashboard-overview', label: 'Overview' },
  { href: '#dashboard-performance', label: 'Performance' },
  { href: '#dashboard-allocation', label: 'Allocation' },
  { href: '#dashboard-health', label: 'Health' },
  { href: '#dashboard-metric-sheet', label: 'Metric Sheet' },
];

const METRIC_OPTIONS = [
  { value: 'value', label: 'Value' },
  { value: 'cumulative_return', label: 'Cumulative Return' },
  { value: 'twror', label: 'TWROR' },
];

const RANGE_OPTIONS = ['7D', '30D', 'YTD', '1Y', '3Y', '5Y', 'ALL'];

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
  return 'neutral';
}

export default function Dashboard() {
  const { apiQuery, selectedPortfolioName, settingsLoaded } = usePortfolio();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [metric, setMetric] = useState('value');
  const [timeRange, setTimeRange] = useState('1Y');
  const [performanceData, setPerformanceData] = useState(null);
  const [seriesLoading, setSeriesLoading] = useState(true);
  const [benchmarkOptions, setBenchmarkOptions] = useState([]);
  const [selectedBenchmark, setSelectedBenchmark] = useState('');
  const [metricSheetData, setMetricSheetData] = useState(null);
  const [metricSheetLoading, setMetricSheetLoading] = useState(true);
  const [metricSheetError, setMetricSheetError] = useState('');
  const summaryRequestIdRef = useRef(0);
  const performanceRequestIdRef = useRef(0);
  const metricSheetRequestIdRef = useRef(0);

  const showBenchmarkPicker =
    metric === 'cumulative_return' || metric === 'twror';

  const shortChartRange = timeRange === '7D' || timeRange === '30D';

  useEffect(() => {
    if (!settingsLoaded || !apiQuery) return;

    const requestId = ++summaryRequestIdRef.current;
    setLoading(true);
    setError('');
    fetchDashboardSummary(apiQuery, { includeTimeseries: false })
      .then((data) => {
        if (requestId !== summaryRequestIdRef.current) return;
        setSummary(data);
        setLoading(false);
      })
      .catch((err) => {
        if (requestId !== summaryRequestIdRef.current) return;
        setError(err.message);
        setLoading(false);
      });
  }, [settingsLoaded, apiQuery]);

  useEffect(() => {
    let cancelled = false;
    fetchBenchmarkIndices()
      .then((rows) => {
        if (cancelled) return;
        setBenchmarkOptions(Array.isArray(rows) ? rows : []);
      })
      .catch(() => {
        if (!cancelled) setBenchmarkOptions([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!settingsLoaded || !apiQuery) return;

    const requestId = ++performanceRequestIdRef.current;
    setSeriesLoading(true);
    const benchParam =
      showBenchmarkPicker && selectedBenchmark ? selectedBenchmark : null;
    fetchPortfolioPerformance(metric, benchParam, timeRange, apiQuery)
      .then((d) => {
        if (requestId !== performanceRequestIdRef.current) return;
        setPerformanceData(d);
        setSeriesLoading(false);
      })
      .catch((e) => {
        if (requestId !== performanceRequestIdRef.current) return;
        setError(e.message);
        setSeriesLoading(false);
      });
  }, [metric, selectedBenchmark, showBenchmarkPicker, timeRange, settingsLoaded, apiQuery]);

  useEffect(() => {
    if (!settingsLoaded || !apiQuery) return;

    const requestId = ++metricSheetRequestIdRef.current;
    setMetricSheetLoading(true);
    setMetricSheetError('');

    const params = {
      ...apiQuery,
      range: timeRange,
    };
    if (selectedBenchmark) {
      params.benchmark = selectedBenchmark;
    }

    getPortfolioMetricSheet(params)
      .then((data) => {
        if (requestId !== metricSheetRequestIdRef.current) return;
        setMetricSheetData(data);
        setMetricSheetLoading(false);
      })
      .catch((err) => {
        if (requestId !== metricSheetRequestIdRef.current) return;
        setMetricSheetError(err.message || 'Failed to load Metric Sheet');
        setMetricSheetData(null);
        setMetricSheetLoading(false);
      });
  }, [settingsLoaded, apiQuery, timeRange, selectedBenchmark]);

  const chartMetricLabel =
    metric === 'value'
      ? 'Value History'
      : metric === 'cumulative_return'
        ? 'Cumulative Return %'
        : 'TWROR %';
  const isPercentMetric = metric !== 'value';
  const displayCurrency = summary?.display_currency || summary?.base_currency || 'EUR';

  const chartConfig = useMemo(
    () =>
      buildDashboardPerformanceChartConfig(performanceData, {
        metric,
        chartMetricLabel,
        displayCurrency,
      }),
    [performanceData, metric, chartMetricLabel, displayCurrency]
  );

  const { chartData, lines, comparisonWarnings } = chartConfig;

  const portfolioTotalsBarData = useMemo(() => {
    if (!summary) return [];
    return [
      {
        label: 'Portfolio',
        invested: Number(summary.total_invested) || 0,
        current: Number(summary.current_value) || 0,
      },
    ];
  }, [summary]);

  const allocationChartData = useMemo(() => {
    const buckets = summary?.allocation_buckets?.buckets;
    if (!Array.isArray(buckets)) return [];
    return buckets.filter((b) => Number(b.value) > 0);
  }, [summary]);

  const allocationTotal = useMemo(
    () => allocationChartData.reduce((sum, b) => sum + (Number(b.value) || 0), 0),
    [allocationChartData]
  );

  const currentBarFill = summary
    ? getComparisonBarFill(summary.current_value, summary.total_invested)
    : getComparisonBarFill(0, 0);

  const benchmarkDelta = metricSheetData?.benchmark?.metrics?.active_return;

  const portfolioHealthItems = useMemo(
    () =>
      buildPortfolioHealthItems({
        summary,
        comparisonWarnings,
        metricSheetWarnings: metricSheetData?.warnings || [],
      }),
    [summary, comparisonWarnings, metricSheetData]
  );

  if (!settingsLoaded || loading) {
    return (
      <LoadingState
        message={
          !settingsLoaded ? 'Loading display settings…' : 'Loading portfolio overview…'
        }
      />
    );
  }
  if (error) return <ErrorState title="Error loading dashboard" message={error} />;
  if (!summary) return null;

  const formatChartValue = (val) => {
    const n = Number(val);
    if (!Number.isFinite(n)) return '';
    const abs = Math.abs(n);
    if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (abs >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toFixed(2);
  };

  const formatAxisMonthYear = (d) => {
    try {
      const dt = new Date(`${d}T00:00:00Z`);
      const mon = new Intl.DateTimeFormat('en-US', { month: 'short' }).format(dt);
      const yy = String(dt.getUTCFullYear() % 100).padStart(2, '0');
      return `${mon}-${yy}`;
    } catch {
      return d;
    }
  };

  const formatAxisDayMonth = (d) => {
    try {
      const dt = new Date(`${d}T00:00:00Z`);
      return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(dt);
    } catch {
      return d;
    }
  };

  const axisDateFormatter = shortChartRange ? formatAxisDayMonth : formatAxisMonthYear;

  const plDiff = Number(summary.current_value) - Number(summary.total_invested);

  const headerSubtitle = [
    selectedPortfolioName || 'All Portfolios',
    displayCurrency,
    'Cached prices, NAVs, benchmarks, and FX',
  ].join(' · ');

  const rangeOptions = RANGE_OPTIONS.map((r) => ({ value: r, label: r }));

  const metricSheetSubtitle = metricSheetData?.range
    ? `Quantitative Statistics · ${metricSheetData.range.code} (${metricSheetData.range.start} – ${metricSheetData.range.end})`
    : `Quantitative Statistics · ${timeRange}`;

  const dataStatusLabel =
    summary.fx_status === 'fx_unavailable' ||
    (summary.warnings?.length ?? 0) > 0 ||
    comparisonWarnings.length > 0
      ? 'Review'
      : 'Good';

  const chartFooter = (
    <>
      {seriesLoading ? (
        <WarningBanner severity="info" message="Loading chart…" />
      ) : null}
      {comparisonWarnings.map((w) => (
        <WarningBanner key={w} severity="warning" message={w} />
      ))}
    </>
  );

  const performanceControls = (
    <ChartControls>
      <SegmentedControl
        ariaLabel="performance-metric"
        options={METRIC_OPTIONS}
        value={metric}
        onChange={setMetric}
      />
      <SegmentedControl
        ariaLabel="performance-time-range"
        options={rangeOptions}
        value={timeRange}
        onChange={setTimeRange}
      />
    </ChartControls>
  );

  const chartLegendItems =
    lines.length > 1 ? buildLegendItems(lines) : [];

  const portfolioLine =
    lines.find((ln) => ln.role === CHART_SERIES_ROLES.portfolio) ?? lines[0];
  const benchmarkDataKeys = lines
    .filter((ln) => ln.role === CHART_SERIES_ROLES.benchmark)
    .map((ln) => ln.dataKey);
  const latestChartReading =
    portfolioLine && chartData.length
      ? findLatestValidChartReading(chartData, portfolioLine.dataKey)
      : null;
  const latestChartValue = latestChartReading?.value ?? null;
  const latestChartDate = latestChartReading?.date ?? null;

  const chartAnimate =
    !seriesLoading && chartData.length > 0 && !error;
  const chartAnimationProps = getChartAnimationProps({ active: chartAnimate });

  const formatChartReadoutValue = (val) => {
    if (val == null || !Number.isFinite(Number(val))) return '—';
    if (isPercentMetric) return `${Number(val).toFixed(2)}%`;
    return formatCurrency(val, displayCurrency);
  };

  return (
    <div className="dashboard">
      <header className="dashboard-hero" id="dashboard-overview">
        <PageHeader
          eyebrow="Whole wealth overview"
          title="Portfolio Overview"
          subtitle={headerSubtitle}
        />
        <div className="dashboard-hero__value" aria-label="Current portfolio value">
          <span className="dashboard-hero__value-label">Current value</span>
          <div className="dashboard-hero__value-amount">
            <CurrencyValue value={summary.current_value} currency={displayCurrency} />
          </div>
          {summary.cash_summary?.total_display_value > 0 ? (
            <p className="dashboard-hero__value-note">Cash-inclusive portfolio value</p>
          ) : null}
        </div>
      </header>

      <nav className="dashboard-section-nav" aria-label="Dashboard section navigation">
        {DASHBOARD_SECTION_NAV.map((item) => (
          <a key={item.href} className="dashboard-section-nav__link" href={item.href}>
            {item.label}
          </a>
        ))}
      </nav>

      <div className="dashboard-kpi-strip" data-testid="dashboard-kpi-strip">
        <KpiCard
          label="Current Value"
          size="compact"
          value={<CurrencyValue value={summary.current_value} currency={displayCurrency} />}
        />
        <KpiCard
          label="Total Invested"
          size="compact"
          value={<CurrencyValue value={summary.total_invested} currency={displayCurrency} />}
        />
        <KpiCard
          label="Total P/L"
          variant={kpiVariantFromTone(plTone(summary.total_pl))}
          value={
            <CurrencyValue
              value={summary.total_pl}
              currency={displayCurrency}
              tone={plTone(summary.total_pl)}
              showSign
            />
          }
        />
        <KpiCard
          label="XIRR"
          variant={kpiVariantFromTone(plTone(summary.xirr))}
          value={<PercentValue value={summary.xirr} tone={plTone(summary.xirr)} showSign />}
        />
        {benchmarkDelta != null ? (
          <KpiCard
            label="Benchmark delta"
            variant={kpiVariantFromTone(plTone(benchmarkDelta))}
            helperText={metricSheetData?.benchmark?.symbol || selectedBenchmark || undefined}
            value={
              <PercentValue
                value={benchmarkDelta}
                tone={plTone(benchmarkDelta)}
                showSign
              />
            }
          />
        ) : null}
        <KpiCard
          label="Data status"
          variant={dataStatusLabel === 'Good' ? 'success' : 'warning'}
          value={dataStatusLabel}
          helperText="Cached data review"
        />
        {summary.realized_pl != null ? (
          <KpiCard
            label="Realized P/L"
            variant={kpiVariantFromTone(plTone(summary.realized_pl))}
            value={
              <CurrencyValue
                value={summary.realized_pl}
                currency={displayCurrency}
                tone={plTone(summary.realized_pl)}
                showSign
              />
            }
          />
        ) : null}
        {summary.unrealized_pl != null ? (
          <KpiCard
            label="Unrealized P/L"
            variant={kpiVariantFromTone(plTone(summary.unrealized_pl))}
            value={
              <CurrencyValue
                value={summary.unrealized_pl}
                currency={displayCurrency}
                tone={plTone(summary.unrealized_pl)}
                showSign
              />
            }
          />
        ) : null}
      </div>

      {summary.fx_status === 'fx_unavailable' ? (
        <WarningBanner
          severity="warning"
          message="FX unavailable for one or more dates."
          className="dashboard-banner"
        />
      ) : null}

      <div className="dashboard-top-fold">
        <div className="dashboard-performance-column" id="dashboard-performance">
          <ChartFrame
            title="Performance Center"
            subtitle={chartMetricLabel}
            density="dashboard"
            footer={chartFooter}
            className="dashboard-performance-center"
            toolbar={performanceControls}
            legend={chartLegendItems.length ? <ChartLegend items={chartLegendItems} /> : null}
            panelClassName="dashboard-chart-panel"
          >
            {metric === 'value' && summary.has_fixed_deposits ? (
              <WarningBanner
                severity="info"
                message="Value chart and return metrics include Fixed Deposits and included Bank Cash where applicable."
                className="dashboard-banner dashboard-banner--inline"
              />
            ) : null}
            {latestChartValue != null ? (
              <div className="dashboard-chart-readout" aria-label="Chart latest value">
                <span className="dashboard-chart-readout__label">{chartMetricLabel}</span>
                <strong className="dashboard-chart-readout__value">
                  {formatChartReadoutValue(latestChartValue)}
                </strong>
                {latestChartDate ? (
                  <span className="dashboard-chart-readout__date">
                    {axisDateFormatter(latestChartDate)} · {timeRange}
                  </span>
                ) : null}
              </div>
            ) : null}
            <ResponsiveContainer width="100%" height={getChartHeight('dashboard')}>
              <LineChart data={chartData} margin={getChartMargin('dashboard')}>
                <CartesianGrid
                  {...getChartGridProps()}
                  vertical={false}
                  strokeOpacity={0.32}
                />
                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  stroke={getChartAxisStroke()}
                  tick={{ ...getChartAxisTick(), fontSize: 11 }}
                  tickFormatter={axisDateFormatter}
                  interval="preserveStartEnd"
                  minTickGap={getChartMinTickGap('dashboard', shortChartRange)}
                  dy={6}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  width={52}
                  stroke={getChartAxisStroke()}
                  tick={{ ...getChartAxisTick(), fontSize: 11 }}
                  tickFormatter={(v) =>
                    isPercentMetric ? `${Number(v).toFixed(1)}%` : formatChartValue(v)
                  }
                />
                <Tooltip
                  content={
                    <ChartRechartsTooltip
                      labelFormatter={axisDateFormatter}
                      valueKind={isPercentMetric ? 'percent' : 'currency'}
                      currency={displayCurrency}
                      benchmarkKeys={benchmarkDataKeys}
                    />
                  }
                  cursor={getChartCrosshairCursorProps('dashboard')}
                />
                {portfolioLine ? (
                  <Area
                    type="monotone"
                    dataKey={portfolioLine.dataKey}
                    stroke="none"
                    fill={getSeriesColorForRole(CHART_SERIES_ROLES.portfolio)}
                    fillOpacity={isPercentMetric ? 0.08 : 0.14}
                    {...chartAnimationProps}
                  />
                ) : null}
                {lines.map((ln) => {
                  const strokeProps = getSeriesStrokeProps(ln.role);
                  return (
                    <Line
                      key={ln.dataKey}
                      type="monotone"
                      dataKey={ln.dataKey}
                      name={ln.name}
                      stroke={ln.stroke}
                      strokeWidth={strokeProps.strokeWidth}
                      strokeDasharray={strokeProps.strokeDasharray}
                      strokeOpacity={strokeProps.strokeOpacity}
                      dot={false}
                      activeDot={getChartActiveDotProps(ln.role)}
                      connectNulls={false}
                      {...chartAnimationProps}
                    />
                  );
                })}
              </LineChart>
            </ResponsiveContainer>
            {!seriesLoading && chartData.length === 0 ? (
              <ChartEmptyState
                title="No performance data for this portfolio."
                className="dashboard-chart-empty"
              />
            ) : null}
          </ChartFrame>
        </div>

        <aside className="dashboard-side-rail" aria-label="Dashboard supporting insights">
          <div id="dashboard-allocation">
          <DashboardAllocationPreview
            buckets={allocationChartData}
            currency={summary.allocation_buckets?.currency || displayCurrency}
            total={allocationTotal}
          />
          </div>
          <div id="dashboard-health">
          <DashboardPortfolioHealth items={portfolioHealthItems} />
          </div>
        </aside>
      </div>

      <section className="dashboard-lower-scroll" aria-label="Dashboard analytics">
        <SectionHeader
          title="Operating View"
          subtitle="Metric Sheet, allocation context, and portfolio totals lower in the scroll."
          className="dashboard-lower-scroll__header"
        />

        <MetricSheetSection
          id="dashboard-metric-sheet"
          className="dashboard-metric-sheet"
          subtitle={metricSheetSubtitle}
          actions={
            <select
              aria-label="metric-sheet-benchmark"
              className="metric-sheet__benchmark-select dashboard-metric-sheet__benchmark-select"
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
          }
        >
          {metricSheetLoading ? (
            <LoadingState message="Loading Metric Sheet…" variant="skeleton" />
          ) : metricSheetError ? (
            <ErrorState title="Metric Sheet unavailable" message={metricSheetError} />
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
                drawdownSeries={metricSheetData.drawdown_series}
              />
            </>
          ) : null}
        </MetricSheetSection>

        <ChartFrame
          title="Invested vs Current"
          subtitle="Portfolio totals comparison"
          density="compact"
          compact
          className="dashboard-invested-current"
          panelClassName="dashboard-chart-panel dashboard-chart-panel--compact"
        >
          <ResponsiveContainer width="100%" height={getChartHeight('compact')}>
            <BarChart
              layout="vertical"
              data={portfolioTotalsBarData}
              margin={{ top: 8, right: 24, left: 72, bottom: 8 }}
            >
              <CartesianGrid {...getChartGridProps()} horizontal={false} />
              <XAxis
                type="number"
                stroke={getChartAxisStroke()}
                tick={getChartAxisTick()}
                tickFormatter={(v) => formatChartValue(v)}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={68}
                stroke={getChartAxisStroke()}
                tick={{ ...getChartAxisTick(), fontSize: 11 }}
              />
              <Tooltip
                contentStyle={getChartTooltipStyle()}
                formatter={(value, name) => [
                  formatCurrency(Number(value), displayCurrency),
                  name,
                ]}
                labelFormatter={() =>
                  `Δ ${plDiff >= 0 ? '+' : ''}${formatCurrency(plDiff, displayCurrency)}`
                }
              />
              <Legend wrapperStyle={getChartLegendStyle()} />
              <Bar dataKey="invested" name="Total Invested" fill={getChartBarInvestedColor()} />
              <Bar dataKey="current" name="Current Value" fill={currentBarFill} />
            </BarChart>
          </ResponsiveContainer>
        </ChartFrame>
      </section>
    </div>
  );
}
