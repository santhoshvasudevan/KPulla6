import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Dashboard from './Dashboard';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', () => ({
  fetchDashboardSummary: vi.fn(),
  fetchPortfolioPerformance: vi.fn(),
  fetchBenchmarkIndices: vi.fn(),
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
    Line: () => <div />,
    Bar: ({ dataKey, fill }) => (
      <div data-testid={`bar-${dataKey}`} data-fill={fill} />
    ),
    XAxis: ({ tickFormatter }) => <div data-testid="x-axis">{tickFormatter ? tickFormatter('2026-01-01') : ''}</div>,
    CartesianGrid: () => <div />,
    Legend: () => <div data-testid="chart-legend" />,
    YAxis: ({ tickFormatter }) => <div data-testid="y-axis">{tickFormatter ? tickFormatter(1234.567) : ''}</div>,
    Tooltip: ({ formatter }) => {
      const formatted = formatter ? formatter(987.654) : '';
      return <div data-testid="chart-tooltip">{Array.isArray(formatted) ? formatted[0] : formatted}</div>;
    },
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
  ]
};

const mockPerf = [
  { date: '2026-01-01', value: 100, metric: 'value', currency: 'EUR' },
  { date: '2026-01-02', value: 110, metric: 'value', currency: 'EUR' },
];

describe('Dashboard Component', () => {
  beforeEach(() => {
    api.fetchDashboardSummary.mockReset();
    api.fetchPortfolioPerformance.mockReset();
    api.fetchBenchmarkIndices.mockReset();
    api.fetchPortfolios?.mockReset?.();
    api.fetchPortfolioPerformance.mockResolvedValue([]);
    api.fetchBenchmarkIndices.mockResolvedValue([
      { symbol: '^GSPC', name: 'S&P 500' },
      { symbol: '^IXIC', name: 'Nasdaq Composite' },
    ]);
    api.fetchPortfolios?.mockResolvedValue?.([]);
    api.getSettings?.mockResolvedValue?.({ display_currency: 'EUR' });
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
      expect(screen.getByText('XIRR')).toBeInTheDocument();
      expect(screen.getByText(/€18,500\.00/)).toBeInTheDocument();
      expect(screen.getByText(/€3,500\.00/)).toBeInTheDocument();
    });
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
      expect(api.fetchDashboardSummary).toHaveBeenCalledWith({ portfolio_id: 2, display_currency: 'EUR' });
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

  it('does not show benchmark index selector for Value History', async () => {
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

  it('shows benchmark index selector for Cumulative Return %', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Cumulative Return' }));
    await waitFor(() => {
      expect(screen.getByLabelText('benchmark-indices')).toBeInTheDocument();
      expect(api.fetchBenchmarkIndices).toHaveBeenCalled();
    });
  });

  it('shows benchmark index selector for TWROR', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValueOnce(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    fireEvent.click(await screen.findByRole('button', { name: 'TWROR' }));
    await waitFor(() => {
      expect(screen.getByLabelText('benchmark-indices')).toBeInTheDocument();
    });
  });

  it('selecting a benchmark calls performance with benchmark parameter (preserves scope/range/display currency)', async () => {
    api.fetchDashboardSummary.mockResolvedValueOnce(mockSummary);
    api.fetchPortfolioPerformance.mockResolvedValue(mockPerf);
    render(
      <PortfolioProvider>
        <Dashboard />
      </PortfolioProvider>
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Cumulative Return' }));

    const benchSel = await screen.findByLabelText('benchmark-indices');
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
      expect(screen.getByTestId('chart-legend')).toBeInTheDocument();
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
      expect(api.fetchDashboardSummary).toHaveBeenCalledWith({
        portfolio_scope: 'all',
        display_currency: 'INR',
      });
    });
    await waitFor(() => {
      expect(api.fetchPortfolioPerformance).toHaveBeenCalledWith('value', null, '1Y', {
        portfolio_scope: 'all',
        display_currency: 'INR',
      });
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
});
