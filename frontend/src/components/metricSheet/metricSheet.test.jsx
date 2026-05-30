import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import {
  MetricSheetSection,
  MetricSheetSummaryCards,
  MetricSheetRiskReturnTable,
  MetricSheetBenchmarkTable,
  MetricSheetWarnings,
  MetricSheetPeriodicReturnsTable,
  MetricSheetMonthlyReturnsGrid,
  MetricSheetDrawdownPeriodsTable,
  CompareMetricTable,
  ComparePeriodicReturnsSection,
  CompareDrawdownPeriodsSection,
  CompareNormalizedChart,
  samplePortfolioMetricSheetPayload,
  sampleCompareMetricSheetPayload,
  mergeNormalizedCompareSeries,
} from './index';
import { METRIC_EM_DASH } from '../../utils/metricFormatters';

describe('MetricSheetSummaryCards', () => {
  it('renders return metric labels and formatted fractions', () => {
    render(<MetricSheetSummaryCards metrics={samplePortfolioMetricSheetPayload.metrics} />);
    expect(screen.getByText('Cumulative Return')).toBeInTheDocument();
    expect(screen.getByText('CAGR')).toBeInTheDocument();
    expect(screen.getByText('TWROR')).toBeInTheDocument();
    expect(screen.getByText('XIRR')).toBeInTheDocument();
    expect(screen.getByText('+12.34%')).toBeInTheDocument();
  });

  it('shows XIRR full-scope note when xirr_scope is full_scope', () => {
    render(<MetricSheetSummaryCards metrics={samplePortfolioMetricSheetPayload.metrics} />);
    expect(
      screen.getByText('XIRR is full-scope; other Metric Sheet values follow the selected range.')
    ).toBeInTheDocument();
  });
});

describe('MetricSheetRiskReturnTable', () => {
  it('renders risk, drawdown, and period metric labels', () => {
    render(<MetricSheetRiskReturnTable metrics={samplePortfolioMetricSheetPayload.metrics} />);
    expect(screen.getByText('Risk')).toBeInTheDocument();
    expect(screen.getByText('Volatility (annualized)')).toBeInTheDocument();
    expect(screen.getByText('Sharpe Ratio')).toBeInTheDocument();
    expect(screen.getByText('Drawdown')).toBeInTheDocument();
    expect(screen.getByText('Max Drawdown')).toBeInTheDocument();
    expect(screen.getByText('Period')).toBeInTheDocument();
    expect(screen.getByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('1.24')).toBeInTheDocument();
    expect(screen.getByText('42 days')).toBeInTheDocument();
  });
});

describe('MetricSheetBenchmarkTable', () => {
  it('renders benchmark metrics when present', () => {
    render(<MetricSheetBenchmarkTable benchmark={samplePortfolioMetricSheetPayload.benchmark} />);
    expect(screen.getByText('Benchmark:')).toBeInTheDocument();
    expect(screen.getByText('^GSPC')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('252')).toBeInTheDocument();
  });

  it('handles null benchmark metrics gracefully', () => {
    render(
      <MetricSheetBenchmarkTable
        benchmark={{ symbol: '^GSPC', paired_count: 0, metrics: null }}
      />
    );
    expect(screen.getByText('Relative metrics')).toBeInTheDocument();
    expect(screen.getAllByText(METRIC_EM_DASH).length).toBeGreaterThan(0);
  });
});

describe('MetricSheetWarnings', () => {
  it('renders backend warning messages', () => {
    render(<MetricSheetWarnings warnings={samplePortfolioMetricSheetPayload.warnings} />);
    expect(screen.getByText(/split-adjusted/i)).toBeInTheDocument();
  });

  it('renders FX and benchmark overlap warnings', () => {
    render(
      <MetricSheetWarnings
        warnings={[
          'FX unavailable for one or more dates in range.',
          'Insufficient overlapping benchmark daily returns for comparison metrics.',
        ]}
      />
    );
    expect(screen.getByText(/fx unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/insufficient overlapping benchmark/i)).toBeInTheDocument();
  });

  it('renders nothing when warnings empty', () => {
    const { container } = render(<MetricSheetWarnings warnings={[]} />);
    expect(container.firstChild).toBeNull();
  });
});

describe('MetricSheetMonthlyReturnsGrid', () => {
  it('renders year rows and month columns with formatted backend values', () => {
    render(
      <MetricSheetMonthlyReturnsGrid
        monthly={[
          { period: '2026-01', return: 0.021 },
          { period: '2026-02', return: -0.012 },
        ]}
        yearly={[{ period: '2026', return: 0.143 }]}
      />
    );

    expect(screen.getByRole('columnheader', { name: 'Jan' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Dec' })).toBeInTheDocument();
    expect(screen.getByRole('rowheader', { name: '2026' })).toBeInTheDocument();
    expect(screen.getByText('+2.10%')).toBeInTheDocument();
    expect(screen.getByText('−1.20%')).toBeInTheDocument();
    expect(screen.getByText('+14.30%')).toBeInTheDocument();
  });

  it('shows empty state when monthly array is empty', () => {
    render(
      <MetricSheetMonthlyReturnsGrid monthly={[]} yearly={[{ period: '2026', return: 0.05 }]} />
    );
    expect(
      screen.getByText(/no monthly return data available for this range/i)
    ).toBeInTheDocument();
  });

  it('uses backend yearly return in year column without computing totals', () => {
    render(
      <MetricSheetMonthlyReturnsGrid
        monthly={[{ period: '2026-01', return: 0.021 }]}
        yearly={[{ period: '2026', return: 0.099 }]}
      />
    );
    expect(screen.getByText('+9.90%')).toBeInTheDocument();
    expect(screen.getByText('+2.10%')).toBeInTheDocument();
  });

  it('renders em dash for missing months', () => {
    render(
      <MetricSheetMonthlyReturnsGrid monthly={[{ period: '2026-01', return: 0.01 }]} yearly={[]} />
    );
    expect(screen.getAllByText(METRIC_EM_DASH).length).toBeGreaterThan(0);
  });
});

describe('MetricSheetPeriodicReturnsTable', () => {
  it('renders monthly grid and yearly total column from backend fractions', () => {
    render(
      <MetricSheetPeriodicReturnsTable
        periodicReturns={samplePortfolioMetricSheetPayload.periodic_returns}
      />
    );
    expect(screen.getByText('Periodic returns')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Jan' })).toBeInTheDocument();
    expect(screen.getByText('+2.10%')).toBeInTheDocument();
    expect(screen.getByText('−1.20%')).toBeInTheDocument();
    expect(screen.getByText('+14.30%')).toBeInTheDocument();
  });

  it('shows inline empty message when monthly array is empty', () => {
    render(
      <MetricSheetPeriodicReturnsTable
        periodicReturns={{ monthly: [], yearly: [{ period: '2026', return: 0.05 }] }}
      />
    );
    expect(
      screen.getByText(/no monthly return data available for this range/i)
    ).toBeInTheDocument();
    expect(screen.getByText('+5.00%')).toBeInTheDocument();
  });

  it('handles missing periodic_returns without crashing', () => {
    render(<MetricSheetPeriodicReturnsTable />);
    expect(
      screen.getByText(/no monthly return data available for this range/i)
    ).toBeInTheDocument();
  });
});

describe('MetricSheetDrawdownPeriodsTable', () => {
  it('renders recovered and unrecovered drawdown rows', () => {
    render(
      <MetricSheetDrawdownPeriodsTable
        drawdownPeriods={samplePortfolioMetricSheetPayload.drawdown_periods}
      />
    );
    expect(screen.getByText('Worst drawdowns')).toBeInTheDocument();
    expect(screen.getByText('2025-06-10')).toBeInTheDocument();
    expect(screen.getByText('2025-08-20')).toBeInTheDocument();
    expect(screen.getByText('Recovered')).toBeInTheDocument();
    expect(screen.getByText('Unrecovered')).toBeInTheDocument();
    expect(screen.getByText('−18.20%')).toBeInTheDocument();
  });

  it('shows em dash for null recovery date', () => {
    render(
      <MetricSheetDrawdownPeriodsTable
        drawdownPeriods={samplePortfolioMetricSheetPayload.drawdown_periods}
      />
    );
    const dashes = screen.getAllByText(METRIC_EM_DASH);
    expect(dashes.length).toBeGreaterThan(0);
  });

  it('wraps drawdown table rows in horizontal scroll container', () => {
    const { container } = render(
      <MetricSheetDrawdownPeriodsTable
        drawdownPeriods={samplePortfolioMetricSheetPayload.drawdown_periods}
      />
    );
    expect(container.querySelector('.metric-sheet-table-scroll')).toBeInTheDocument();
  });

  it('handles missing drawdown_periods without crashing', () => {
    render(<MetricSheetDrawdownPeriodsTable />);
    expect(
      screen.getByText(/no drawdown period data available for this range/i)
    ).toBeInTheDocument();
  });
});

describe('ComparePeriodicReturnsSection', () => {
  it('renders yearly returns side by side per subject', () => {
    render(<ComparePeriodicReturnsSection subjects={sampleCompareMetricSheetPayload.subjects} />);
    expect(screen.getByText('Periodic returns')).toBeInTheDocument();
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByText('Microsoft Corp.')).toBeInTheDocument();
    expect(screen.getByText('+5.00%')).toBeInTheDocument();
    expect(screen.getByText('+4.00%')).toBeInTheDocument();
  });
});

describe('CompareDrawdownPeriodsSection', () => {
  it('renders per-subject worst drawdown tables', () => {
    render(<CompareDrawdownPeriodsSection subjects={sampleCompareMetricSheetPayload.subjects} />);
    expect(screen.getByText('Worst drawdowns')).toBeInTheDocument();
    expect(screen.getByText('Recovered')).toBeInTheDocument();
    expect(screen.getByText('Unrecovered')).toBeInTheDocument();
  });
});

describe('CompareMetricTable', () => {
  it('renders side-by-side return and risk metrics from API', () => {
    render(
      <CompareMetricTable
        subjects={sampleCompareMetricSheetPayload.subjects}
        showBenchmark
      />
    );
    expect(screen.getByText('Cumulative Return')).toBeInTheDocument();
    expect(screen.getByText('+12.34%')).toBeInTheDocument();
    expect(screen.getByText('Sharpe')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });
});

describe('mergeNormalizedCompareSeries', () => {
  it('maps backend normalized_series without transforming values', () => {
    const { chartData } = mergeNormalizedCompareSeries(
      sampleCompareMetricSheetPayload.normalized_series
    );
    expect(chartData[0]['asset:AAPL']).toBe(0);
    expect(chartData[1]['asset:MSFT']).toBe(0.0567);
  });
});

describe('CompareNormalizedChart', () => {
  it('renders empty state when series is empty', () => {
    render(<CompareNormalizedChart normalizedSeries={[]} subjects={[]} />);
    expect(screen.getByText(/no comparison chart data/i)).toBeInTheDocument();
  });
});

describe('MetricSheetSection', () => {
  it('wraps children in section card', () => {
    render(
      <MetricSheetSection subtitle="Quantitative Statistics">
        <p>Body content</p>
      </MetricSheetSection>
    );
    expect(screen.getByRole('heading', { name: 'Metric Sheet' })).toBeInTheDocument();
    expect(screen.getByText('Quantitative Statistics')).toBeInTheDocument();
    expect(screen.getByText('Body content')).toBeInTheDocument();
  });
});
