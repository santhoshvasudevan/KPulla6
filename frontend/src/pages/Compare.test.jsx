import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Compare from './Compare';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';
import sampleCompareMetricSheetPayload from '../components/metricSheet/fixtures/sampleCompareMetricSheetPayload';
import { mergeNormalizedCompareSeries } from '../components/metricSheet/CompareNormalizedChart';

vi.mock('../api', () => ({
  fetchHoldings: vi.fn(),
  fetchBenchmarkIndices: vi.fn(),
  getCompareMetricSheet: vi.fn(),
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

vi.mock('recharts', async () => {
  return {
    ResponsiveContainer: ({ children }) => <div data-testid="recharts-wrapper">{children}</div>,
    LineChart: ({ data, children }) => (
      <div data-testid="compare-line-chart" data-points={data?.length ?? 0}>
        {children}
      </div>
    ),
    Line: ({ dataKey, name }) => (
      <div data-testid={`line-${dataKey}`} data-name={name} />
    ),
    XAxis: () => <div />,
    YAxis: ({ tickFormatter }) => (
      <div data-testid="y-axis">{tickFormatter ? tickFormatter(0.1234) : ''}</div>
    ),
    CartesianGrid: () => <div />,
    Legend: () => <div data-testid="chart-legend" />,
    Tooltip: ({ formatter }) => {
      const formatted = formatter ? formatter(0.1234) : '';
      return <div data-testid="chart-tooltip">{formatted}</div>;
    },
  };
});

const holdingsTwo = {
  holdings: [
    { asset_symbol: 'AAPL', asset_type: 'STOCK', quantity: 10, current_value: 1000 },
    { asset_symbol: 'MSFT', asset_type: 'STOCK', quantity: 5, current_value: 500 },
  ],
};

const holdingsOne = {
  holdings: [{ asset_symbol: 'AAPL', asset_type: 'STOCK', quantity: 10, current_value: 1000 }],
};

function renderCompare(route = '/compare') {
  return render(
    <PortfolioProvider>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/compare" element={<Compare />} />
        </Routes>
      </MemoryRouter>
    </PortfolioProvider>
  );
}

describe('Compare page', () => {
  beforeEach(() => {
    api.fetchHoldings.mockReset();
    api.fetchBenchmarkIndices.mockReset();
    api.getCompareMetricSheet.mockReset();
    api.fetchPortfolios?.mockReset?.();
    api.getSettings?.mockResolvedValue?.({ display_currency: 'EUR' });
    api.fetchPortfolios?.mockResolvedValue?.([]);
    api.fetchBenchmarkIndices.mockResolvedValue([
      { symbol: '^GSPC', name: 'S&P 500' },
    ]);
    api.fetchHoldings.mockResolvedValue(holdingsTwo);
    api.getCompareMetricSheet.mockResolvedValue(sampleCompareMetricSheetPayload);
  });

  it('renders Compare route with subject pickers from holdings', async () => {
    renderCompare();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /compare assets/i })).toBeInTheDocument();
      expect(screen.getByText('Comparison setup')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument();
    expect(screen.getByLabelText('compare-asset-b')).toBeInTheDocument();
    expect(screen.getByLabelText('compare-asset-a')).toHaveTextContent('AAPL');
    expect(screen.getByLabelText('compare-asset-b')).toHaveTextContent('MSFT');
    expect(screen.getByRole('link', { name: /setup/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^chart$/i })).toBeInTheDocument();
  });

  it('shows selected subject chips after picking assets', async () => {
    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('compare-asset-a'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('compare-asset-b'), { target: { value: 'MSFT' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/selected comparison subjects/i)).toBeInTheDocument();
      expect(screen.getByText(/asset a: aapl/i)).toBeInTheDocument();
      expect(screen.getByText(/asset b: msft/i)).toBeInTheDocument();
    });
  });

  it('calls getCompareMetricSheet with asset subjects when two assets selected', async () => {
    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).not.toBeDisabled());

    fireEvent.change(screen.getByLabelText('compare-asset-a'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('compare-asset-b'), { target: { value: 'MSFT' } });

    await waitFor(() => expect(api.getCompareMetricSheet).toHaveBeenCalled());
    const params = api.getCompareMetricSheet.mock.calls.at(-1)[0];
    expect(params.subjects).toBe('asset:AAPL,asset:MSFT');
    expect(params.range).toBe('1Y');
    expect(params.portfolio_scope).toBe('all');
    expect(params.display_currency).toBe('EUR');
  });

  it('prevents comparing the same asset and shows validation', async () => {
    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText('compare-asset-a'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('compare-asset-b'), { target: { value: 'AAPL' } });

    expect(screen.getByText(/select two different assets/i)).toBeInTheDocument();
    expect(api.getCompareMetricSheet).not.toHaveBeenCalled();
  });

  it('renders normalized chart from backend series without client-side math', async () => {
    const { chartData } = mergeNormalizedCompareSeries(
      sampleCompareMetricSheetPayload.normalized_series
    );
    expect(chartData[0]['asset:AAPL']).toBe(0);
    expect(chartData[1]['asset:AAPL']).toBe(0.1234);

    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('compare-asset-a'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('compare-asset-b'), { target: { value: 'MSFT' } });

    await waitFor(() => expect(screen.getByTestId('compare-line-chart')).toBeInTheDocument());
    expect(screen.getByText('Normalized Cumulative Return')).toBeInTheDocument();
    expect(screen.getByLabelText(/comparison summary/i)).toBeInTheDocument();
    expect(screen.getByTestId('compare-line-chart')).toHaveAttribute('data-points', '2');
    expect(screen.getByTestId('line-asset:AAPL')).toHaveAttribute('data-name', 'Apple Inc.');
    expect(screen.getByTestId('chart-tooltip')).toHaveTextContent('+12.34%');
  });

  it('renders compare periodic returns and worst drawdown sections', async () => {
    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('compare-asset-a'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('compare-asset-b'), { target: { value: 'MSFT' } });

    await waitFor(() => {
      expect(screen.getByText('Periodic returns')).toBeInTheDocument();
      expect(screen.getByText('Worst drawdowns')).toBeInTheDocument();
      expect(screen.getAllByText('+5.00%').length).toBeGreaterThan(0);
      expect(screen.getByText('Unrecovered')).toBeInTheDocument();
    });
  });

  it('renders side-by-side metrics from API payload values', async () => {
    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('compare-asset-a'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('compare-asset-b'), { target: { value: 'MSFT' } });

    await waitFor(() => expect(screen.getByText('Metric Sheet comparison')).toBeInTheDocument());
    expect(screen.getAllByText('+12.34%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('+5.67%').length).toBeGreaterThan(0);
    expect(screen.getByText('1.10')).toBeInTheDocument();
  });

  it('renders global and subject warnings', async () => {
    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('compare-asset-a'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('compare-asset-b'), { target: { value: 'MSFT' } });

    await waitFor(() =>
      expect(
        screen.getByText(/compare api metrics are computed over common overlapping dates only/i)
      ).toBeInTheDocument()
    );
    expect(screen.getByText(/subject-specific warning for aapl/i)).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('Requested range: 1Y');
    expect(screen.getByRole('note')).toHaveTextContent(
      'Compared over common dates: 2025-06-01 to 2026-05-30'
    );
  });

  it('labels closed holdings and lists active before closed', async () => {
    api.fetchHoldings.mockResolvedValueOnce({
      holdings: [
        { asset_symbol: 'OLD', quantity: 0, holding_status: 'closed' },
        { asset_symbol: 'AAPL', quantity: 10, holding_status: 'open' },
        { asset_symbol: 'MSFT', quantity: 5, holding_status: 'open' },
      ],
    });
    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument());
    const selectA = screen.getByLabelText('compare-asset-a');
    expect(selectA).toHaveTextContent('OLD (closed)');
    const options = [...selectA.querySelectorAll('option')].map((o) => o.textContent);
    const aaplIdx = options.indexOf('AAPL');
    const oldIdx = options.indexOf('OLD (closed)');
    expect(aaplIdx).toBeGreaterThan(-1);
    expect(oldIdx).toBeGreaterThan(aaplIdx);
  });

  it('passes benchmark param and renders benchmark metrics when selected', async () => {
    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('compare-asset-a'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('compare-asset-b'), { target: { value: 'MSFT' } });
    fireEvent.change(screen.getByLabelText('compare-benchmark'), { target: { value: '^GSPC' } });

    await waitFor(() => expect(api.getCompareMetricSheet).toHaveBeenCalled());
    const withBench = api.getCompareMetricSheet.mock.calls.find((c) => c[0].benchmark === '^GSPC');
    expect(withBench).toBeTruthy();

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Benchmark', level: 4 })).toBeInTheDocument()
    );
    expect(screen.getAllByText('1.05').length).toBeGreaterThan(0);
  });

  it('does not include cash rows in compare pickers', async () => {
    api.fetchHoldings.mockResolvedValueOnce({
      holdings: [
        { asset_symbol: 'AAPL', asset_type: 'STOCK', quantity: 10, current_value: 1000 },
        {
          asset_symbol: 'Cash EUR',
          asset_type: 'CASH',
          is_cash: true,
          quantity: 0,
          current_value: 500,
        },
        { asset_symbol: 'MSFT', asset_type: 'STOCK', quantity: 5, current_value: 500 },
      ],
    });
    renderCompare();
    await waitFor(() => {
      expect(screen.getByLabelText('compare-asset-a')).toHaveTextContent('AAPL');
      expect(screen.getByLabelText('compare-asset-b')).toHaveTextContent('MSFT');
    });
    expect(screen.getByLabelText('compare-asset-a')).not.toHaveTextContent('Cash EUR');
  });

  it('shows empty state when fewer than two holdings', async () => {
    api.fetchHoldings.mockResolvedValueOnce(holdingsOne);
    renderCompare();
    await waitFor(() => {
      expect(screen.getByText(/need at least two assets/i)).toBeInTheDocument();
    });
    expect(api.getCompareMetricSheet).not.toHaveBeenCalled();
  });

  it('shows friendly message for MF multi-folio backend error', async () => {
    api.getCompareMetricSheet.mockRejectedValueOnce(
      new Error('folio_number is required when multiple folios exist for this scheme')
    );
    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('compare-asset-a'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('compare-asset-b'), { target: { value: 'MSFT' } });

    await waitFor(() =>
      expect(
        screen.getByText(/this mutual fund has multiple folios/i)
      ).toBeInTheDocument()
    );
  });

  it('shows empty chart state when normalized_series is empty', async () => {
    api.getCompareMetricSheet.mockResolvedValueOnce({
      ...sampleCompareMetricSheetPayload,
      normalized_series: [],
    });
    renderCompare();
    await waitFor(() => expect(screen.getByLabelText('compare-asset-a')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('compare-asset-a'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('compare-asset-b'), { target: { value: 'MSFT' } });

    await waitFor(() =>
      expect(screen.getByText(/no comparison chart data/i)).toBeInTheDocument()
    );
  });
});
