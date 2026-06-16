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
  MetricCard,
  CurrencyValue,
  PercentValue,
  LoadingState,
  ErrorState,
  WarningBanner,
  ChartCard,
  SegmentedControl,
  EmptyState,
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
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import {
  getSeriesColor,
  getBenchmarkLineColors,
  getComparisonBarFill,
  getChartGridProps,
  getChartAxisStroke,
  getChartAxisTick,
  getChartTooltipStyle,
  getChartLegendStyle,
  getChartBarInvestedColor,
} from '../components/charts/chartTheme';
import './Dashboard.css';

const METRIC_OPTIONS = [
  { value: 'value', label: 'Value' },
  { value: 'cumulative_return', label: 'Cumulative Return' },
  { value: 'twror', label: 'TWROR' },
];

const RANGE_OPTIONS = ['7D', '30D', 'YTD', '1Y', '3Y', '5Y', 'ALL'];

function mergeComparisonSeries(payload) {
  const byDate = new Map();
  for (const s of payload.series || []) {
    const key = s.name;
    for (const pt of s.data || []) {
      if (!byDate.has(pt.date)) byDate.set(pt.date, { date: pt.date });
      byDate.get(pt.date)[key] = pt.value;
    }
  }
  return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
}

function plTone(val) {
  if (val == null || Number.isNaN(Number(val))) return 'neutral';
  const n = Number(val);
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
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

  const chartTitle =
    metric === 'value'
      ? 'Value History'
      : metric === 'cumulative_return'
        ? 'Cumulative Return %'
        : 'TWROR %';
  const isPercentMetric = metric !== 'value';
  const displayCurrency = summary?.display_currency || summary?.base_currency || 'EUR';

  const chartConfig = useMemo(() => {
    if (!performanceData) {
      return { chartData: [], lines: [], comparisonWarnings: [] };
    }
    const isComparisonPayload =
      typeof performanceData === 'object' &&
      !Array.isArray(performanceData) &&
      Array.isArray(performanceData.series);
    const isValueWithWarnings =
      typeof performanceData === 'object' &&
      !Array.isArray(performanceData) &&
      Array.isArray(performanceData.points);
    if (isComparisonPayload) {
      const chartData = mergeComparisonSeries(performanceData);
      const benchmarkColors = getBenchmarkLineColors();
      const lines = (performanceData.series || []).map((s, i) => ({
        dataKey: s.name,
        name: s.name,
        stroke: benchmarkColors[i % benchmarkColors.length],
      }));
      return {
        chartData,
        lines,
        comparisonWarnings: performanceData.warnings || [],
      };
    }
    const arr = Array.isArray(performanceData)
      ? performanceData
      : isValueWithWarnings
        ? performanceData.points
        : [];
    const chartData = arr.map((p) => ({
      date: p.date,
      value: p.value,
      currency: p.currency || displayCurrency,
    }));
    return {
      chartData,
      lines: [
        {
          dataKey: 'value',
          name: chartTitle,
          stroke: getSeriesColor(0),
        },
      ],
      comparisonWarnings: isValueWithWarnings ? performanceData.warnings || [] : [],
    };
  }, [performanceData, chartTitle, displayCurrency]);

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
  ].join(' · ');

  const rangeOptions = RANGE_OPTIONS.map((r) => ({ value: r, label: r }));

  const metricSheetSubtitle = metricSheetData?.range
    ? `Quantitative Statistics · ${metricSheetData.range.code} (${metricSheetData.range.start} – ${metricSheetData.range.end})`
    : `Quantitative Statistics · ${timeRange}`;

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

  return (
    <div className="dashboard">
      <PageHeader title="Portfolio Overview" subtitle={headerSubtitle} />

      <div className="dashboard-kpi-grid">
        <MetricCard
          label="Current Value"
          size="hero"
          value={
            <CurrencyValue value={summary.current_value} currency={displayCurrency} />
          }
        />
        <MetricCard
          label="Total Invested"
          value={
            <CurrencyValue value={summary.total_invested} currency={displayCurrency} />
          }
        />
        <MetricCard
          label="Total P/L"
          tone={plTone(summary.total_pl)}
          value={
            <CurrencyValue
              value={summary.total_pl}
              currency={displayCurrency}
              tone={plTone(summary.total_pl)}
              showSign
            />
          }
        />
        <MetricCard
          label="XIRR"
          tone={plTone(summary.xirr)}
          value={
            <PercentValue
              value={summary.xirr}
              tone={plTone(summary.xirr)}
              showSign
            />
          }
        />
        {summary.realized_pl != null ? (
          <MetricCard
            label="Realized P/L"
            tone={plTone(summary.realized_pl)}
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
          <MetricCard
            label="Unrealized P/L"
            tone={plTone(summary.unrealized_pl)}
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

      {allocationChartData.length > 0 && allocationTotal > 0 ? (
        <ChartCard
          title="Asset allocation"
          subtitle="Equity / Debt / Other from backend summary"
          className="dashboard-allocation-card"
          compact
        >
          <div className="dashboard-allocation-panel">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={allocationChartData}
                  dataKey="value"
                  nameKey="label"
                  outerRadius={80}
                  label={({ label, percent }) =>
                    `${label} ${(percent * 100).toFixed(0)}%`
                  }
                >
                  {allocationChartData.map((entry, index) => (
                    <Cell key={entry.label} fill={getSeriesColor(index)} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(val) =>
                    formatCurrency(Number(val), summary.allocation_buckets?.currency || displayCurrency)
                  }
                  contentStyle={getChartTooltipStyle()}
                />
                <Legend wrapperStyle={getChartLegendStyle()} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      ) : null}

      <div className="dashboard-charts">
        <ChartCard
          title={chartTitle}
          footer={chartFooter}
        >
          {metric === 'value' && summary.has_fixed_deposits ? (
            <WarningBanner
              severity="info"
              message="Value chart and return metrics include Fixed Deposits and included Bank Cash where applicable."
              className="dashboard-banner"
            />
          ) : null}
          <div className="dashboard-chart-controls">
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
          </div>
          <div className="dashboard-chart-panel">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid {...getChartGridProps()} />
                <XAxis
                  dataKey="date"
                  stroke={getChartAxisStroke()}
                  tick={getChartAxisTick()}
                  tickFormatter={axisDateFormatter}
                  interval="preserveStartEnd"
                  minTickGap={shortChartRange ? 8 : 24}
                />
                <YAxis
                  stroke={getChartAxisStroke()}
                  tick={getChartAxisTick()}
                  tickFormatter={(v) =>
                    isPercentMetric ? `${Number(v).toFixed(2)}%` : formatChartValue(v)
                  }
                />
                <Tooltip
                  contentStyle={getChartTooltipStyle()}
                  formatter={(value) => {
                    if (value == null) return 'N/A';
                    return isPercentMetric
                      ? `${Number(value).toFixed(2)}%`
                      : formatCurrency(value, displayCurrency);
                  }}
                  labelFormatter={(l) => axisDateFormatter(l)}
                />
                {lines.length > 1 ? (
                  <Legend wrapperStyle={getChartLegendStyle()} />
                ) : null}
                {lines.map((ln) => (
                  <Line
                    key={ln.dataKey}
                    type="monotone"
                    dataKey={ln.dataKey}
                    name={ln.name}
                    stroke={ln.stroke}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                    connectNulls={ln.name === 'Portfolio'}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
            {!seriesLoading && chartData.length === 0 ? (
              <EmptyState
                title="No performance data for this portfolio."
                className="dashboard-chart-empty"
              />
            ) : null}
          </div>
        </ChartCard>
      </div>

      <MetricSheetSection
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

      <div className="dashboard-charts dashboard-charts--secondary">
        <ChartCard
          title="Invested vs Current"
          subtitle="Portfolio totals comparison"
          compact
        >
          <div className="dashboard-chart-panel dashboard-chart-panel--compact">
            <ResponsiveContainer width="100%" height={120}>
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
          </div>
        </ChartCard>
      </div>
    </div>
  );
}
