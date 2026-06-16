import { render, screen, waitFor, fireEvent, act, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useEffect } from 'react';
import Dashboard from './Dashboard';
import * as api from '../api';
import { PortfolioProvider, usePortfolio } from '../portfolioContext';
import samplePortfolioMetricSheetPayload from '../components/metricSheet/fixtures/samplePortfolioMetricSheetPayload';

vi.mock('../api', () => ({
  fetchDashboardSummary: vi.fn(),
  fetchPortfolioPerformance: vi.fn(),
  fetchBenchmarkIndices: vi.fn(),
  getPortfolioMetricSheet: vi.fn(),
  fetchTransactions: vi.fn(),
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

vi.mock('recharts', async () => {
  return {
    ResponsiveContainer: ({ children }) => <div data-testid="recharts-wrapper">{children}</div>,
    LineChart: ({ children }) => <div>{children}</div>,
    BarChart: ({ children }) => <div>{children}</div>,
    AreaChart: ({ children }) => <div data-testid="area-chart">{children}</div>,
    Line: () => <div />,
    Bar: ({ children, dataKey, fill }) => (
      <div data-testid={`bar-${dataKey}`} data-fill={fill}>
        {children}
      </div>
    ),
    Cell: ({ fill }) => <div data-testid="bar-cell" data-fill={fill} />,
    Area: () => <div data-testid="area" />,
    ReferenceArea: ({ className }) => (
      <div className={className} data-testid="reference-area" />
    ),
    XAxis: ({ tickFormatter }) => <div data-testid="x-axis">{tickFormatter ? tickFormatter('2026-01-01') : ''}</div>,
    CartesianGrid: () => <div />,
    Legend: () => <div data-testid="chart-legend" />,
    YAxis: ({ tickFormatter }) => <div data-testid="y-axis">{tickFormatter ? tickFormatter(1234.567) : ''}</div>,
    Tooltip: ({ formatter }) => {
      const formatted = formatter ? formatter(987.654) : '';
      return <div data-testid="chart-tooltip">{Array.isArray(formatted) ? formatted[0] : formatted}</div>;
    },
    PieChart: ({ children }) => <div data-testid="pie-chart">{children}</div>,
    Pie: ({ children }) => <div data-testid="pie">{children}</div>,
  };
});

const mockSummary = {
  base_currency: 'EUR',
  fx_status: 'ok',
  total_invested: 15000,
  current_value: 18500,
  realized_pl: 500,
  unrealized_pl: 3000,
  total_pl: 3500,
  xirr: 0.125,
  holdings: [
    { asset_symbol: 'AAA', quantity: 1, invested: 10000, current_value: 11000 },
    { asset_symbol: 'BBB', quantity: 2, invested: 5000, current_value: 7500 },
  ],
  timeseries: [
    { date: '2026-05-01', portfolio_value: 18000, invested_amount: 15000 },
    { date: '2026-05-02', portfolio_value: 18500, invested_amount: 15000 }
  ],
  allocation_buckets: {
    currency: 'EUR',
    fx_status: 'ok',
    buckets: [
      { label: 'Equity', value: 12000 },
      { label: 'Debt', value: 5000 },
      { label: 'Other', value: 1500 },
    ],
  },
};

const mockPerf = [
  { date: '2026-01-01', value: 100, metric: 'value', currency: 'EUR' },
  { date: '2026-01-02', value: 110, metric: 'value', currency: 'EUR' },
];

const DASHBOARD_SUMMARY_OPTS = { includeTimeseries: false };

const mockMetricSheet = { ...samplePortfolioMetricSheetPayload };

describe('Dashboard Component', () => {
  beforeEach(() => {
    api.fetchDashboardSummary.mockReset();
    api.fetchPortfolioPerformance.mockReset();
    api.fetchBenchmarkIndices.mockReset();
    api.getPortfolioMetricSheet.mockReset();
    api.fetchPortfolios?.mockReset?.();
    api.fetchPortfolioPerformance.mockResolvedValue([]);
    api.getPortfolioMetricSheet.mockResolvedValue(mockMetricSheet);
    api.fetchBenchmarkIndices.mockResolvedValue([
      { symbol: '^GSPC', name: 'S&P 500' },
      { symbol: '^IXIC', name: 'Nasdaq Composite' },
    ]);
    api.fetchPortfolios?.mockResolvedValue?.([]);
    api.getSettings?.mockResolvedValue?.({ display_currency: 'EUR' });
  });

  it('renders summary current value including cash from backend fixture', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce({
      ...mockSummary,
      current_value: 19700,
      cash_summary: {
        display_currency: 'EUR',
        total_display_value: 1200,
        balances: [
          {
            portfolio_id: 1,
            portfolio_name: 'Default',
            currency: 'EUR',
            native_balance: 1200,
            display_value: 1200,
          },
        ],
      },
    });
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/€19,700\.00/)).toBeInTheDocument();
    });
  });

  it('shows a loading state initially', () => {
    api.fetchDashboardSummary.mockReturnValueOnce(new Promise(() => {})); // never resolves
    api.fetchPortfolioPerformance.mockReturnValueOnce(new Promise(() => {}));
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders summary cards after data loads', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Current Value')).toBeInTheDocument();
      expect(screen.getByText('Total Invested')).toBeInTheDocument();
      expect(screen.getByText('Total P/L')).toBeInTheDocument();
      expect(within(document.querySelector('.dashboard-kpi-grid')).getByText('XIRR')).toBeInTheDocument();
      expect(screen.getByText(/€18,500\.00/)).toBeInTheDocument();
      expect(screen.getByText(/€3,500\.00/)).toBeInTheDocument();
    });
  });

  it('renders Cash / Bank Cash allocation bucket from backend', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce({
      ...mockSummary,
      allocation_buckets: {
        currency: 'EUR',
        fx_status: 'ok',
        buckets: [
          { label: 'Equity', value: 12000 },
          { label: 'Debt', value: 5000 },
          { label: 'Cash / Bank Cash', value: 2500 },
          { label: 'Other', value: 1500 },
        ],
      },
    });
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Asset allocation')).toBeInTheDocument();
      expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
    });
  });

  it('renders allocation chart from backend allocation_buckets', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Asset allocation')).toBeInTheDocument();
      expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
    });
  });

  it('shows FD value-chart note when summary has FDs', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce({
      ...mockSummary,
      has_fixed_deposits: true,
    });
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/value chart and return metrics include fixed deposits/i)
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByText(/return metrics may still exclude/i)
    ).not.toBeInTheDocument();
  });

  it('displays XIRR as a percentage', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('+12.50%')).toBeInTheDocument();
    });
  });

  it('renders charts after data loads', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getAllByTestId('recharts-wrapper').length).toBeGreaterThan(0);
    });
  });

  it('shows an error state on API failure', async () => {
    api.fetchDashboardSummary.mockRejectedValueOnce(new Error('Network error'));
    api.fetchPortfolioPerformance.mockResolvedValueOnce([]);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Network error');
    });
  });

  it('formats value history axis compactly and tooltip values to 2 decimals', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getAllByTestId('y-axis')[0]).toHaveTextContent('1.2K');
      expect(screen.getAllByTestId('chart-tooltip')[0]).toHaveTextContent('987.65');
      expect(screen.getAllByTestId('x-axis')[0]).toHaveTextContent('Jan-26');
    });
  });

  it('renders metric control and calls performance endpoint on change', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    api.fetchPortfolioPerformance.mockResolvedValueOnce([
      { date: '2026-01-01', value: 0, metric: 'twror', currency: 'EUR' },
    ]);

    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    expect(await screen.findByRole('group', { name: 'performance-metric' })).toBeInTheDocument();

    expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith('value', null, '1Y', { portfolio_scope: 'all', display_currency: 'EUR' });
    fireEvent.click(screen.getByRole('button', { name: 'TWROR' }));
    await waitFor(() => {
      expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith('twror', null, '1Y', { portfolio_scope: 'all', display_currency: 'EUR' });
    });
  });

  it('uses portfolio_id when a specific portfolio is selected', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider
        initialPortfolios={[{ id: 2, name: 'Growth', is_active: true, is_default: false }]}
        initialSelection={{ mode: 'portfolio', id: 2, name: 'Growth' }}
        disableFetch
      >
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(api.fetchDashboardSummary).toHaveBeenCalledWith(
        { portfolio_id: 2, display_currency: 'EUR' },
        DASHBOARD_SUMMARY_OPTS
      );
      expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith('value', null, '1Y', { portfolio_id: 2, display_currency: 'EUR' });
    });
  });

  it('renders an empty performance state safely when performance series is empty', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce({
      ...mockSummary,
      total_invested: 0,
      current_value: 0,
      holdings: [],
      timeseries: [],
      xirr: null,
    });
    api.fetchPortfolioPerformance.mockResolvedValueOnce([]);

    render(
      <PortfolioProvider
        initialPortfolios={[{ id: 3, name: 'Empty', is_active: true, is_default: false }]}
        initialSelection={{ mode: 'portfolio', id: 3, name: 'Empty' }}
        disableFetch
      >
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Current Value')).toBeInTheDocument();
      expect(screen.getByText(/No performance data for this portfolio/i)).toBeInTheDocument();
    });
  });

  it('renders time range pills and calls performance with selected range', async () => {
    api.fetchDashboardSummary.mockResolvedValue(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValue(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    await screen.findByRole('group', { name: 'performance-time-range' });
    expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith('value', null, '1Y', { portfolio_scope: 'all', display_currency: 'EUR' });

    const btn30 = screen.getByRole('button', { name: '30D' });
    expect(btn30).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(btn30);
    await waitFor(() => {
      expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith('value', null, '30D', { portfolio_scope: 'all', display_currency: 'EUR' });
    });
    expect(btn30).toHaveAttribute('aria-pressed', 'true');

    const btnYtd = screen.getByRole('button', { name: 'YTD' });
    fireEvent.click(btnYtd);
    await waitFor(() => {
      expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith('value', null, 'YTD', { portfolio_scope: 'all', display_currency: 'EUR' });
    });
  });

  it('metric control and range filter work together', async () => {
    api.fetchDashboardSummary.mockResolvedValue(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValue(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    await screen.findByText('Current Value');
    fireEvent.click(screen.getByRole('button', { name: 'ALL' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cumulative Return' }));
    await waitFor(() => {
      expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith(
        'cumulative_return',
        null,
        'ALL',
        { portfolio_scope: 'all', display_currency: 'EUR' }
      );
    });
  });

  it('Invested vs Current uses portfolio totals only (two bars, no per-asset split)', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('Invested vs Current')).toBeInTheDocument();
    });
    expect(screen.getByTestId('bar-invested')).toBeInTheDocument();
    expect(screen.getByTestId('bar-current')).toBeInTheDocument();
    expect(screen.queryByTestId('bar-AAA')).not.toBeInTheDocument();
  });

  it('Current Value bar is green when ahead of invested, red when behind', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    const { unmount } = render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByTestId('bar-current')).toHaveAttribute('data-fill', '#22c55e');
    });
    unmount();

    api.fetchDashboardSummary.mockResolvedValueOnce({
      ...mockSummary,
      current_value: 12000,
      total_invested: 15000,
    });
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByTestId('bar-current')).toHaveAttribute('data-fill', '#ef4444');
    });
  });

  it('does not show chart benchmark selector for Value History', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.queryByLabelText('benchmark-indices')).not.toBeInTheDocument();
    });
  });

  it('shows Metric Sheet benchmark selector on Value History', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByLabelText('metric-sheet-benchmark')).toBeInTheDocument();
      expect(api.fetchBenchmarkIndices).toHaveBeenCalled();
    });
  });

  it('shows Metric Sheet benchmark selector for Cumulative Return %', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Cumulative Return' }));
    await waitFor(() => {
      expect(screen.getByLabelText('metric-sheet-benchmark')).toBeInTheDocument();
    });
  });

  it('shows Metric Sheet benchmark selector for TWROR', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    fireEvent.click(await screen.findByRole('button', { name: 'TWROR' }));
    await waitFor(() => {
      expect(screen.getByLabelText('metric-sheet-benchmark')).toBeInTheDocument();
    });
  });

  it('selecting a Metric Sheet benchmark calls performance with benchmark when return metric is active', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValue(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Cumulative Return' }));

    const benchSel = await screen.findByLabelText('metric-sheet-benchmark');
    fireEvent.change(benchSel, { target: { value: '^GSPC' } });

    await waitFor(() => {
      expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith(
        'cumulative_return',
        '^GSPC',
        '1Y',
        { portfolio_scope: 'all', display_currency: 'EUR' }
      );
    });
  });

  it('renders benchmark comparison payload (two lines) for return metrics', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce({
      metric: 'cumulative_return',
      series: [
        { type: 'portfolio', name: 'Portfolio', data: [{ date: '2026-01-01', value: 0.0 }] },
        { type: 'benchmark', symbol: '^GSPC', name: 'S&P 500', data: [{ date: '2026-01-01', value: 0.0 }] },
      ],
      warnings: [],
    });
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Cumulative Return' }));

    await waitFor(() => {
      expect(screen.getAllByTestId('chart-legend').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('passes display_currency=INR to summary and performance when settings use INR', async () => {
    api.getSettings.mockResolvedValue({ display_currency: 'INR' });
    api.fetchDashboardSummary.mockResolvedValue({
      ...mockSummary,
      base_currency: 'EUR',
      display_currency: 'INR',
      fx_status: 'ok',
    });
    api.fetchPortfolioPerformance.mockResolvedValue([
      { date: '2026-01-01', value: 9000, metric: 'value', currency: 'INR' },
    ]);

    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(api.fetchDashboardSummary).toHaveBeenCalledWith(
        {
          portfolio_scope: 'all',
          display_currency: 'INR',
        },
        DASHBOARD_SUMMARY_OPTS
      );
    });
    await waitFor(() => {
      expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith('value', null, '1Y', {
        portfolio_scope: 'all',
        display_currency: 'INR',
      });
    });
  });

  it('requests summary without timeseries and still renders KPI cards', async () => {
    api.getSettings.mockResolvedValue({ display_currency: 'EUR' });
    const summaryNoTimeseries = {
      base_currency: 'EUR',
      display_currency: 'EUR',
      fx_status: 'ok',
      total_invested: 15000,
      current_value: 18500,
      realized_pl: 500,
      unrealized_pl: 3000,
      total_pl: 3500,
      xirr: 0.125,
      timeseries: [],
    };
    api.fetchDashboardSummary.mockResolvedValueOnce(summaryNoTimeseries);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);

    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(api.fetchDashboardSummary).toHaveBeenCalledWith(
        expect.objectContaining({ portfolio_scope: 'all', display_currency: 'EUR' }),
        DASHBOARD_SUMMARY_OPTS
      );
      expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith(
        'value',
        null,
        '1Y',
        expect.objectContaining({ portfolio_scope: 'all', display_currency: 'EUR' })
      );
      expect(screen.getByText(/€18,500\.00/)).toBeInTheDocument();
      expect(screen.getByText('Total P/L')).toBeInTheDocument();
    });
  });

  it('renders backend-provided INR values without local conversion', async () => {
    api.getSettings.mockResolvedValue({ display_currency: 'INR' });
    api.fetchDashboardSummary.mockResolvedValue({
      ...mockSummary,
      base_currency: 'EUR',
      display_currency: 'INR',
      fx_status: 'ok',
      current_value: 1665000,
      total_invested: 1350000,
      unrealized_pl: 315000,
      total_pl: 315000,
    });
    api.fetchPortfolioPerformance.mockResolvedValue([
      { date: '2026-01-01', value: 1665000, metric: 'value', currency: 'INR' },
    ]);

    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/₹1,665,000\.00/)).toBeInTheDocument();
      expect(screen.getAllByText(/₹315,000\.00/).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('keeps large INR KPI values on one line inside metric cards', async () => {
    api.getSettings.mockResolvedValue({ display_currency: 'INR' });
    api.fetchDashboardSummary.mockResolvedValue({
      ...mockSummary,
      display_currency: 'INR',
      current_value: 16650000,
      total_invested: 13500000,
      total_pl: 3150000,
    });
    api.fetchPortfolioPerformance.mockResolvedValue([
      { date: '2026-01-01', value: 16650000, metric: 'value', currency: 'INR' },
    ]);

    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByTitle('₹16,650,000.00')).toBeInTheDocument();
      expect(screen.getByTitle('₹13,500,000.00')).toBeInTheDocument();
    });

    expect(screen.getByTitle('₹16,650,000.00').textContent).toBe('₹16,650,000.00');
    expect(screen.getByTitle('₹16,650,000.00').closest('.ui-metric-card__value')).toBeInTheDocument();
  });

  it('does not fetch summary or performance until settings are loaded', async () => {
    let resolveSettings;
    api.getSettings.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSettings = () => resolve({ display_currency: 'INR' });
      })
    );
    api.fetchDashboardSummary.mockResolvedValue({
      ...mockSummary,
      display_currency: 'INR',
    });
    api.fetchPortfolioPerformance.mockResolvedValue(mockPerf);

    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );

    expect(screen.getByText(/loading display settings/i)).toBeInTheDocument();
    expect(api.fetchDashboardSummary).not.toHaveBeenCalled();
    expect(api.fetchPortfolioPerformance).not.toHaveBeenCalled();

    await act(async () => {
      resolveSettings();
    });

    await waitFor(() => {
      expect(api.fetchDashboardSummary).toHaveBeenCalledTimes(1);
      expect(api.fetchDashboardSummary).toHaveBeenCalledWith(
        {
          portfolio_scope: 'all',
          display_currency: 'INR',
        },
        DASHBOARD_SUMMARY_OPTS
      );
    });
    expect(api.fetchDashboardSummary).not.toHaveBeenCalledWith(
      expect.objectContaining({ display_currency: 'EUR' }),
      DASHBOARD_SUMMARY_OPTS
    );
    await waitFor(() => {
      expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith('value', null, '1Y', {
        portfolio_scope: 'all',
        display_currency: 'INR',
      });
    });
  });

  it('ignores stale summary responses when apiQuery changes', async () => {
    api.getSettings.mockResolvedValue({ display_currency: 'INR' });
    api.updateSettings.mockResolvedValue({ display_currency: 'EUR' });

    let resolveInr;
    let resolveEur;
    api.fetchDashboardSummary.mockImplementation((params) => {
      if (params.display_currency === 'INR') {
        return new Promise((resolve) => {
          resolveInr = () =>
            resolve({
              ...mockSummary,
              display_currency: 'INR',
              current_value: 1665000,
            });
        });
      }
      return new Promise((resolve) => {
        resolveEur = () =>
          resolve({
            ...mockSummary,
            display_currency: 'EUR',
            current_value: 8500,
          });
      });
    });
    api.fetchPortfolioPerformance.mockResolvedValue(mockPerf);

    function FlipToEurAfterLoad() {
      const { settingsLoaded, setDisplayCurrency } = usePortfolio();
      useEffect(() => {
        if (!settingsLoaded) return;
        void setDisplayCurrency('EUR');
      }, [settingsLoaded, setDisplayCurrency]);
      return <Dashboard />;
    }

    render(
      <PortfolioProvider>
        <FlipToEurAfterLoad />
      </PortfolioProvider>
    );

    await waitFor(() => expect(api.fetchDashboardSummary).toHaveBeenCalledTimes(2));

    await act(async () => {
      resolveEur();
    });
    await waitFor(() => {
      expect(screen.getByText(/€8,500\.00/)).toBeInTheDocument();
    });

    await act(async () => {
      resolveInr();
    });
    await waitFor(() => {
      expect(screen.getByText(/€8,500\.00/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/₹1,665,000\.00/)).not.toBeInTheDocument();
  });

  it('ignores stale performance responses when apiQuery changes', async () => {
    api.getSettings.mockResolvedValue({ display_currency: 'INR' });
    api.updateSettings.mockResolvedValue({ display_currency: 'EUR' });
    api.fetchDashboardSummary.mockResolvedValue({
      ...mockSummary,
      display_currency: 'EUR',
      current_value: 8500,
    });

    let resolveInrPerf;
    let resolveEurPerf;
    api.fetchPortfolioPerformance.mockImplementation((_metric, _bench, _range, params) => {
      if (params.display_currency === 'INR') {
        return new Promise((resolve) => {
          resolveInrPerf = () => resolve([{ date: '2026-01-01', value: 1665000, currency: 'INR' }]);
        });
      }
      return new Promise((resolve) => {
        resolveEurPerf = () => resolve([{ date: '2026-01-01', value: 8500, currency: 'EUR' }]);
      });
    });

    function FlipToEurAfterLoad() {
      const { settingsLoaded, setDisplayCurrency } = usePortfolio();
      useEffect(() => {
        if (!settingsLoaded) return;
        void setDisplayCurrency('EUR');
      }, [settingsLoaded, setDisplayCurrency]);
      return <Dashboard />;
    }

    render(
      <PortfolioProvider>
        <FlipToEurAfterLoad />
      </PortfolioProvider>
    );

    await waitFor(() => expect(api.fetchPortfolioPerformance).toHaveBeenCalledTimes(2));

    await act(async () => {
      resolveEurPerf();
    });
    await waitFor(() => {
      expect(screen.getByText(/€8,500\.00/)).toBeInTheDocument();
    });

    await act(async () => {
      resolveInrPerf();
    });
    await waitFor(() => {
      expect(screen.getByText(/€8,500\.00/)).toBeInTheDocument();
    });
  });

  describe('Metric Sheet', () => {
    it('calls getPortfolioMetricSheet with scope, range, currency, and benchmark', async () => {
      api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
      api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);

      render(
        <PortfolioProvider>
          <Dashboard />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(api.getPortfolioMetricSheet).toHaveBeenCalledWith({
          portfolio_scope: 'all',
          display_currency: 'EUR',
          range: '1Y',
        });
      });
    });

    it('renders Metric Sheet metrics after successful fetch', async () => {
      api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
      api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);

      render(
        <PortfolioProvider>
          <Dashboard />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Metric Sheet' })).toBeInTheDocument();
      });
      const metricSheetSection = screen
        .getByRole('heading', { name: 'Metric Sheet' })
        .closest('.dashboard-metric-sheet');
      expect(metricSheetSection).toHaveClass('metric-sheet');
      expect(metricSheetSection.closest('.dashboard-charts')).toBeNull();
      expect(within(metricSheetSection).getByText('Cumulative Return')).toBeInTheDocument();
      expect(within(metricSheetSection).getByText('Sharpe Ratio')).toBeInTheDocument();
      expect(within(metricSheetSection).getByText('+12.34%')).toBeInTheDocument();
    });

    it('renders periodic returns and worst drawdown periods from backend', async () => {
      api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
      api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);

      render(
        <PortfolioProvider>
          <Dashboard />
        </PortfolioProvider>
      );

      const metricSheetSection = await waitFor(() => {
        const card = screen
          .getByRole('heading', { name: 'Metric Sheet' })
          .closest('.ui-section-card');
        expect(within(card).getByText('Periodic returns')).toBeInTheDocument();
        expect(within(card).getByText('Calendar-Year Return')).toBeInTheDocument();
        return card;
      });
      expect(within(metricSheetSection).getByText('Worst drawdowns')).toBeInTheDocument();
      expect(
        within(metricSheetSection).getByRole('heading', { name: 'Drawdown', level: 3 })
      ).toBeInTheDocument();
      expect(within(metricSheetSection).getByRole('columnheader', { name: 'Jan' })).toBeInTheDocument();
      expect(within(metricSheetSection).getAllByText('+2.10%').length).toBeGreaterThan(0);
      expect(within(metricSheetSection).getByText('Recovered')).toBeInTheDocument();
    });

    it('handles Metric Sheet payload without periodic_returns or drawdown_periods', async () => {
      api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
      api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
      const { periodic_returns: _p, drawdown_periods: _d, ...legacy } = mockMetricSheet;
      api.getPortfolioMetricSheet.mockResolvedValueOnce(legacy);

      render(
        <PortfolioProvider>
          <Dashboard />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Metric Sheet' })).toBeInTheDocument();
      });
      expect(
        screen.getByText(/no monthly return data available for this range/i)
      ).toBeInTheDocument();
    });

    it('displays backend Metric Sheet warnings', async () => {
      api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
      api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
      api.getPortfolioMetricSheet.mockResolvedValueOnce(mockMetricSheet);

      render(
        <PortfolioProvider>
          <Dashboard />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByText(/split-adjusted/i)).toBeInTheDocument();
      });
    });

    it('shows em dash for null metric values', async () => {
      api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
      api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
      api.getPortfolioMetricSheet.mockResolvedValueOnce({
        ...mockMetricSheet,
        metrics: {
          return: {
            cumulative_return: null,
            cagr: null,
            xirr: null,
            xirr_scope: 'full_scope',
            twror: null,
          },
          risk: {
            volatility_annualized: null,
            downside_deviation: null,
            sharpe_ratio: null,
            sortino_ratio: null,
          },
          drawdown: {
            max_drawdown: null,
            longest_drawdown_days: null,
            calmar_ratio: null,
          },
          periods: {
            best_day: null,
            worst_day: null,
            win_rate: null,
            average_daily_return: null,
          },
        },
        benchmark: null,
        warnings: ['Insufficient daily returns to compute risk metrics.'],
      });

      render(
        <PortfolioProvider>
          <Dashboard />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getAllByText('—').length).toBeGreaterThan(0);
        expect(screen.getByText('Volatility (annualized)')).toBeInTheDocument();
      });
    });

    it('Metric Sheet failure does not break the Dashboard', async () => {
      api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
      api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
      api.getPortfolioMetricSheet.mockRejectedValueOnce(new Error('Analytics unavailable'));

      render(
        <PortfolioProvider>
          <Dashboard />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Current Value')).toBeInTheDocument();
        expect(screen.getByText('Metric Sheet unavailable')).toBeInTheDocument();
        expect(screen.getByText('Analytics unavailable')).toBeInTheDocument();
      });
      expect(screen.queryByRole('alert', { name: /error loading dashboard/i })).not.toBeInTheDocument();
    });

    it('refetches Metric Sheet when range changes', async () => {
      api.fetchDashboardSummary.mockResolvedValue(mockSummary);
      api.fetchPortfolioPerformance.mockResolvedValue(mockPerf);

      render(
        <PortfolioProvider>
          <Dashboard />
        </PortfolioProvider>
      );

      await screen.findByRole('group', { name: 'performance-time-range' });
      fireEvent.click(screen.getByRole('button', { name: '30D' }));

      await waitFor(() => {
        expect(api.getPortfolioMetricSheet).toHaveBeenCalledWith(
          expect.objectContaining({ range: '30D' })
        );
      });
    });

    it('passes benchmark to Metric Sheet when benchmark is selected', async () => {
      api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
      api.fetchPortfolioPerformance.mockResolvedValue(mockPerf);

      render(
        <PortfolioProvider>
          <Dashboard />
        </PortfolioProvider>
      );

      const benchSel = await screen.findByLabelText('metric-sheet-benchmark');
      fireEvent.change(benchSel, { target: { value: '^GSPC' } });

      await waitFor(() => {
        expect(api.getPortfolioMetricSheet).toHaveBeenCalledWith(
          expect.objectContaining({
            portfolio_scope: 'all',
            display_currency: 'EUR',
            range: '1Y',
            benchmark: '^GSPC',
          })
        );
      });
    });

    it('ignores stale Metric Sheet responses when apiQuery changes', async () => {
      api.getSettings.mockResolvedValue({ display_currency: 'INR' });
      api.updateSettings.mockResolvedValue({ display_currency: 'EUR' });
      api.fetchDashboardSummary.mockResolvedValue({
        ...mockSummary,
        display_currency: 'EUR',
        current_value: 8500,
      });
      api.fetchPortfolioPerformance.mockResolvedValue(mockPerf);

      let resolveInrSheet;
      let resolveEurSheet;
      api.getPortfolioMetricSheet.mockImplementation((params) => {
        if (params.display_currency === 'INR') {
          return new Promise((resolve) => {
            resolveInrSheet = () =>
              resolve({
                ...mockMetricSheet,
                metrics: {
                  ...mockMetricSheet.metrics,
                  return: {
                    ...mockMetricSheet.metrics.return,
                    cumulative_return: 0.99,
                  },
                },
              });
          });
        }
        return new Promise((resolve) => {
          resolveEurSheet = () =>
            resolve({
              ...mockMetricSheet,
              metrics: {
                ...mockMetricSheet.metrics,
                return: {
                  ...mockMetricSheet.metrics.return,
                  cumulative_return: 0.1234,
                },
              },
            });
        });
      });

      function FlipToEurAfterLoad() {
        const { settingsLoaded, setDisplayCurrency } = usePortfolio();
        useEffect(() => {
          if (!settingsLoaded) return;
          void setDisplayCurrency('EUR');
        }, [settingsLoaded, setDisplayCurrency]);
        return <Dashboard />;
      }

      render(
        <PortfolioProvider>
          <FlipToEurAfterLoad />
        </PortfolioProvider>
      );

      await waitFor(() => expect(api.getPortfolioMetricSheet).toHaveBeenCalledTimes(2));

      const metricSheetSection = () =>
        screen.getByRole('heading', { name: 'Metric Sheet' }).closest('.ui-section-card');

      await act(async () => {
        resolveEurSheet();
      });
      await waitFor(() => {
        expect(within(metricSheetSection()).getByText('+12.34%')).toBeInTheDocument();
      });

      await act(async () => {
        resolveInrSheet();
      });
      await waitFor(() => {
        expect(within(metricSheetSection()).getByText('+12.34%')).toBeInTheDocument();
      });
      expect(within(metricSheetSection()).queryByText('+99.00%')).not.toBeInTheDocument();
    });
  });
});
