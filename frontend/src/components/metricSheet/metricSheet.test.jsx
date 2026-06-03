import { render, screen, within } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import {
  MetricSheetSection,
  MetricSheetSummaryCards,
  MetricSheetRiskReturnTable,
  MetricSheetBenchmarkTable,
  MetricSheetWarnings,
  MetricSheetPeriodicReturnsTable,
  MetricSheetMonthlyReturnsGrid,
  MetricSheetYearlyReturnChart,
  MetricSheetDrawdownChart,
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

function metricCompareRow(label) {
  const heading = screen.getByRole('rowheader', { name: label });
  return heading.closest('tr');
}

describe('MetricSheetSummaryCards', () => {
  it('renders return metric labels and formatted fractions', () => {
    render(<MetricSheetSummaryCards metrics={samplePortfolioMetricSheetPayload.metrics} />);
    expect(screen.getByText('Cumulative Return')).toBeInTheDocument();
    expect(screen.getByText('CAGR')).toBeInTheDocument();
    expect(screen.getByText('TWROR')).toBeInTheDocument();
    expect(screen.getByText('XIRR')).toBeInTheDocument();
    expect(screen.getByText('+12.34%')).toBeInTheDocument();
  });

  it('does not reuse TWROR for cumulative return or CAGR', () => {
    render(
      <MetricSheetSummaryCards
        metrics={{
          return: {
            cumulative_return: 0.6224,
            cagr: 0.58,
            twror: 0.6924,
            xirr: 0.3888,
            xirr_scope: 'full_scope',
          },
        }}
      />
    );
    expect(screen.getByText('+62.24%')).toBeInTheDocument();
    expect(screen.getByText('+69.24%')).toBeInTheDocument();
    expect(screen.getByText('+38.88%')).toBeInTheDocument();
    expect(screen.getByText('+58.00%')).toBeInTheDocument();
    const percents = screen.getAllByText(/^[+-]\d+\.\d{2}%$/);
    expect(percents.map((el) => el.textContent)).toEqual(
      expect.arrayContaining(['+62.24%', '+58.00%', '+69.24%', '+38.88%'])
    );
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
    expect(screen.getByRole('heading', { name: 'Drawdown' })).toBeInTheDocument();
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

  it('renders missing stock price and MF NAV warnings with warning severity', () => {
    const { container } = render(
      <MetricSheetWarnings
        warnings={[
          'Cached prices are missing for one or more dates; Metric Sheet values may be unavailable.',
          'Latest cached NAV is older than 5 days for one or more mutual funds; run NAV sync to refresh valuations.',
        ]}
      />
    );
    expect(screen.getByText(/cached prices are missing/i)).toBeInTheDocument();
    expect(screen.getByText(/latest cached nav is older than 5 days/i)).toBeInTheDocument();
    expect(container.querySelectorAll('.ui-banner--warning')).toHaveLength(2);
  });

  it('uses info severity for compare common-window notice', () => {
    const { container } = render(
      <MetricSheetWarnings
        warnings={['Compare API metrics are computed over common overlapping dates only.']}
      />
    );
    expect(container.querySelector('.ui-banner--info')).toBeInTheDocument();
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
    expect(screen.getByRole('columnheader', { name: 'Year Return' })).toBeInTheDocument();
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

  it('applies heatmap tone classes for strong positive, neutral, and strong negative', () => {
    const { container } = render(
      <MetricSheetMonthlyReturnsGrid
        monthly={[
          { period: '2026-01', return: 0.12 },
          { period: '2026-02', return: 0.01 },
          { period: '2026-03', return: -0.12 },
        ]}
        yearly={[]}
      />
    );
    expect(
      container.querySelector('.metric-sheet-monthly-grid__cell--strong-positive')
    ).toBeInTheDocument();
    expect(container.querySelector('.metric-sheet-monthly-grid__cell--neutral')).toBeInTheDocument();
    expect(
      container.querySelector('.metric-sheet-monthly-grid__cell--strong-negative')
    ).toBeInTheDocument();
    expect(screen.getByText('+12.00%')).toBeInTheDocument();
    expect(screen.getByText('−12.00%')).toBeInTheDocument();
  });
});

describe('MetricSheetYearlyReturnChart', () => {
  it('renders backend yearly return values as a bar chart', () => {
    const { container } = render(
      <MetricSheetYearlyReturnChart
        yearly={[
          { period: '2024', return: -0.02 },
          { period: '2025', return: 0.143 },
        ]}
      />
    );
    expect(screen.getByRole('heading', { name: 'Calendar-Year Return' })).toBeInTheDocument();
    expect(
      screen.getByText('Cash-flow adjusted return using daily TWROR.')
    ).toBeInTheDocument();
    expect(container.querySelector('.metric-sheet-chart-panel')).toBeInTheDocument();
  });

  it('shows empty message when yearly returns are empty', () => {
    render(<MetricSheetYearlyReturnChart yearly={[]} />);
    expect(
      screen.getByText(/no calendar-year return data available for this range/i)
    ).toBeInTheDocument();
  });
});

describe('MetricSheetDrawdownChart', () => {
  it('renders backend drawdown series and applies rank shading classes', () => {
    const { container } = render(
      <MetricSheetDrawdownChart
        drawdownSeries={samplePortfolioMetricSheetPayload.drawdown_series}
        drawdownPeriods={samplePortfolioMetricSheetPayload.drawdown_periods}
      />
    );
    expect(screen.getByRole('heading', { name: 'Drawdown' })).toBeInTheDocument();
    expect(container.querySelector('.metric-sheet-chart-panel')).toBeInTheDocument();
    expect(
      container.querySelector('[data-drawdown-regions="true"]')
    ).toBeInTheDocument();
    expect(
      container.querySelector('[data-drawdown-ranks="1,2"]')
    ).toBeInTheDocument();
  });

  it('shows empty message when drawdown series is empty', () => {
    render(
      <MetricSheetDrawdownChart
        drawdownSeries={[]}
        drawdownPeriods={samplePortfolioMetricSheetPayload.drawdown_periods}
      />
    );
    expect(
      screen.getByText(/no drawdown series data available for this range/i)
    ).toBeInTheDocument();
  });

  it('renders series without shaded regions when worst periods are empty', () => {
    const { container } = render(
      <MetricSheetDrawdownChart
        drawdownSeries={samplePortfolioMetricSheetPayload.drawdown_series}
        drawdownPeriods={{ worst: [] }}
      />
    );
    expect(container.querySelector('[data-drawdown-regions="false"]')).toBeInTheDocument();
  });
});

describe('MetricSheetPeriodicReturnsTable', () => {
  it('renders monthly grid and yearly total column from backend fractions', () => {
    render(
      <MetricSheetPeriodicReturnsTable
        periodicReturns={samplePortfolioMetricSheetPayload.periodic_returns}
      />
    );
    expect(screen.getByText('Calendar-Year Return')).toBeInTheDocument();
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

  it('wraps yearly fallback table in horizontal scroll container', () => {
    const { container } = render(
      <MetricSheetPeriodicReturnsTable
        periodicReturns={{ monthly: [], yearly: [{ period: '2026', return: 0.05 }] }}
      />
    );
    expect(container.querySelector('.metric-sheet-table-scroll')).toBeInTheDocument();
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
        drawdownSeries={samplePortfolioMetricSheetPayload.drawdown_series}
      />
    );
    expect(screen.getByRole('heading', { name: 'Drawdown' })).toBeInTheDocument();
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

  it('shows empty message when no yearly data exists', () => {
    render(
      <ComparePeriodicReturnsSection
        subjects={sampleCompareMetricSheetPayload.subjects.map((subj) => ({
          ...subj,
          periodic_returns: { monthly: [], yearly: [] },
        }))}
      />
    );
    expect(
      screen.getByText(/no yearly return data available for this comparison/i)
    ).toBeInTheDocument();
  });
});

describe('CompareDrawdownPeriodsSection', () => {
  it('renders per-subject worst drawdown tables', () => {
    render(<CompareDrawdownPeriodsSection subjects={sampleCompareMetricSheetPayload.subjects} />);
    expect(screen.getByText('Worst drawdowns')).toBeInTheDocument();
    expect(screen.getByText('Recovered')).toBeInTheDocument();
    expect(screen.getByText('Unrecovered')).toBeInTheDocument();
  });

  it('wraps drawdown tables in horizontal scroll containers', () => {
    const { container } = render(
      <CompareDrawdownPeriodsSection subjects={sampleCompareMetricSheetPayload.subjects} />
    );
    expect(container.querySelectorAll('.metric-sheet-table-scroll').length).toBeGreaterThan(0);
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
    expect(screen.getByText('Sharpe Ratio')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });

  it('shows XIRR full-scope note when xirr_scope is full_scope', () => {
    render(<CompareMetricTable subjects={sampleCompareMetricSheetPayload.subjects} />);
    expect(
      screen.getByText('XIRR is full-scope; other Metric Sheet values follow the selected range.')
    ).toBeInTheDocument();
  });

  it('renders highlight note for metric comparison', () => {
    render(
      <CompareMetricTable subjects={sampleCompareMetricSheetPayload.subjects} showBenchmark />
    );
    expect(
      screen.getByText(/subtle highlights indicate the stronger value where metric direction is clear/i)
    ).toBeInTheDocument();
  });

  it('highlights higher-is-better metrics on the stronger subject cell', () => {
    render(<CompareMetricTable subjects={sampleCompareMetricSheetPayload.subjects} />);
    const cumulativeRow = metricCompareRow('Cumulative Return');
    const cells = within(cumulativeRow).getAllByRole('cell');
    expect(cells[0]).toHaveClass('compare-metric-value--better');
    expect(cells[1]).toHaveClass('compare-metric-value--worse');
  });

  it('highlights lower volatility on the lower subject cell', () => {
    render(<CompareMetricTable subjects={sampleCompareMetricSheetPayload.subjects} />);
    const volatilityRow = metricCompareRow('Volatility (annualized)');
    const cells = within(volatilityRow).getAllByRole('cell');
    expect(cells[0]).toHaveClass('compare-metric-value--worse');
    expect(cells[1]).toHaveClass('compare-metric-value--better');
  });

  it('treats less negative max drawdown as better', () => {
    render(<CompareMetricTable subjects={sampleCompareMetricSheetPayload.subjects} />);
    const drawdownRow = metricCompareRow('Max Drawdown');
    const cells = within(drawdownRow).getAllByRole('cell');
    expect(cells[0]).toHaveClass('compare-metric-value--worse');
    expect(cells[1]).toHaveClass('compare-metric-value--better');
  });

  it('leaves beta and correlation cells without highlight classes', () => {
    render(
      <CompareMetricTable subjects={sampleCompareMetricSheetPayload.subjects} showBenchmark />
    );
    for (const label of ['Beta', 'Correlation']) {
      const row = metricCompareRow(label);
      for (const cell of within(row).getAllByRole('cell')) {
        expect(cell.className).not.toMatch(/compare-metric-value--/);
      }
    }
  });

  it('leaves null XIRR neutral without highlighting the present value', () => {
    render(<CompareMetricTable subjects={sampleCompareMetricSheetPayload.subjects} />);
    const xirrRow = metricCompareRow('XIRR');
    for (const cell of within(xirrRow).getAllByRole('cell')) {
      expect(cell.className).not.toMatch(/compare-metric-value--/);
    }
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
