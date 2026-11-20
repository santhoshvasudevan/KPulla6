import { render, screen, waitFor, fireEvent, within, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import AssetDetail from './AssetDetail';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';
import samplePortfolioMetricSheetPayload from '../components/metricSheet/fixtures/samplePortfolioMetricSheetPayload';

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
}

vi.mock('../api', () => ({
  fetchAssetDetails: vi.fn(),
  fetchHoldings: vi.fn().mockResolvedValue({ holdings: [] }),
  getAssetMetricSheet: vi.fn(),
  fetchBenchmarkIndices: vi.fn(),
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

const mockAssetDetail = {
  asset_symbol: 'A',
  currency: 'EUR',
  current_price: 130,
  current_value: 910,
  cumulative_qty: 7,
  cumulative_invested_amount: 800,
  avg_cost_per_share: 114.2857,
  realized_pl: 240,
  unrealized_pl: 110,
  xirr: 0.125,
  transactions: [],
};

const mockMetricSheet = { ...samplePortfolioMetricSheetPayload };

function renderDetail(route = '/assets/A') {
  return render(
    <PortfolioProvider disableFetch initialPortfolios={[]}>
      <MemoryRouter initialEntries={[route]}>
        <LocationProbe />
        <Routes>
          <Route path="/assets/:assetSymbol" element={<AssetDetail />} />
        </Routes>
      </MemoryRouter>
    </PortfolioProvider>
  );
}

describe('AssetDetail Page', () => {
  beforeEach(() => {
    api.fetchAssetDetails.mockReset();
    api.getAssetMetricSheet.mockReset();
    api.fetchBenchmarkIndices.mockReset();
    api.getAssetMetricSheet.mockResolvedValue(mockMetricSheet);
    api.fetchBenchmarkIndices.mockResolvedValue([
      { symbol: '^GSPC', name: 'S&P 500' },
    ]);
  });

  it('renders tear-sheet header, KPIs, and section navigation', async () => {
    api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);

    renderDetail();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'A' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Assets' })).toBeInTheDocument();
      expect(screen.getByLabelText('Asset class: Stock')).toBeInTheDocument();
      expect(screen.getByRole('navigation', { name: 'Asset detail section navigation' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Metrics' })).toHaveAttribute('href', '#asset-metrics');
    });
    expect(within(document.querySelector('.asset-detail-kpi-grid')).getByText('+12.50%')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText('XIRR', { exact: true })).toHaveLength(2);
    });
    expect(screen.queryByText('Your Holding XIRR')).not.toBeInTheDocument();
  });

  it('renders returned metrics', async () => {
    api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);

    renderDetail();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'A' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Assets' })).toBeInTheDocument();
      expect(screen.getAllByText(/€800\.00/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/€114\.29/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/€240\.00/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/€110\.00/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/€130\.00/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/€910\.00/).length).toBeGreaterThan(0);
      expect(within(document.querySelector('.asset-detail-kpi-grid')).getByText('+12.50%')).toBeInTheDocument();
    });
  });

  it.each([0.2876, 0, null])('separates MF NAV performance from native-INR personal XIRR %s', async (xirr) => {
    api.fetchAssetDetails.mockResolvedValueOnce({
      ...mockAssetDetail, asset_type: 'MUTUAL_FUND',
    });
    api.getAssetMetricSheet.mockResolvedValueOnce({
      ...mockMetricSheet,
      performance_basis: 'nav', currency: 'INR',
      metrics: { ...mockMetricSheet.metrics, return: { cumulative_return: 0.00568975, xirr: null } },
      personal_metrics: {
        xirr, xirr_scope: 'full_scope',
        status: xirr == null ? 'unavailable' : 'calculated',
        basis: 'native_inr',
        warnings: [],
      },
      coverage: { partial_months: ['2024-03'], partial_years: ['2024'] },
      periodic_returns: {
        monthly: [{ period: '2024-03', return: 0.00568975 }],
        yearly: [{ period: '2024', return: 0.00568975 }],
      },
    });
    renderDetail();
    await screen.findByRole('heading', { name: 'Fund Performance — INR' });
    const position = screen.getByRole('region', { name: 'Your Position' });
    expect(within(position).getByText('Your Holding XIRR')).toBeInTheDocument();
    expect(within(position).getByText(xirr == null ? '—' : xirr === 0 ? '0.00%' : '+28.76%')).toBeInTheDocument();
    expect(within(position).getByText(/annualized personal return in INR/i)).toBeInTheDocument();
    const header = document.querySelector('.asset-detail-kpi-grid');
    expect(within(header).getByText('Your Holding XIRR')).toBeInTheDocument();
    expect(within(header).getByText('+12.50%')).toBeInTheDocument();
    expect(within(header).getByText(/annualized personal return in INR/i)).toBeInTheDocument();
    expect(screen.queryByText('XIRR', { exact: true })).not.toBeInTheDocument();
    expect(screen.getByRole('cell', { name: /March 2024.*0.57%/i })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: /2024 year return/i })).toBeInTheDocument();
    expect(screen.queryByText(/partial/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('cell', { name: /partial/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('cell', { name: /2024 full-year return/i })).not.toBeInTheDocument();
    expect(screen.getByText('Cumulative NAV Return')).toBeInTheDocument();
    expect(screen.queryByText('TWROR', { exact: true })).not.toBeInTheDocument();
    expect(screen.queryByText('Cash-flow adjusted return using daily TWROR.')).not.toBeInTheDocument();
    expect(within(header).getByText(/€910\.00/)).toBeInTheDocument();
  });


  it('opens the selected folio when a scheme has multiple positions', async () => {
    api.fetchAssetDetails
      .mockRejectedValueOnce(new Error('folio_number is required when multiple folios exist for this scheme'))
      .mockResolvedValueOnce({ ...mockAssetDetail, folio_number: 'F/2' });
    api.fetchHoldings.mockResolvedValueOnce({ holdings: [
      { scheme_code: '119288', folio_number: 'F/1' },
      { scheme_code: '119288', folio_number: 'F/2' },
      { scheme_code: '120503', folio_number: 'Other' },
    ] });
    renderDetail('/assets/119288');
    const picker = await screen.findByRole('combobox', { name: 'Folio' });
    expect(within(picker).queryByText('Other')).not.toBeInTheDocument();
    fireEvent.change(picker, { target: { value: 'F/2' } });
    await screen.findByText('Position / Cost Basis');
    expect(api.fetchAssetDetails).toHaveBeenLastCalledWith(
      '119288', expect.objectContaining({ portfolio_scope: 'all' }), 'F/2'
    );
  });

  it('clears stale folio picker choices when the asset symbol changes', async () => {
    api.fetchAssetDetails
      .mockRejectedValueOnce(new Error('folio_number is required when multiple folios exist for this scheme'))
      .mockRejectedValueOnce(new Error('folio_number is required when multiple folios exist for this scheme'));
    api.fetchHoldings
      .mockResolvedValueOnce({ holdings: [
        { scheme_code: '119288', folio_number: 'OLD-1' },
        { scheme_code: '119288', folio_number: 'OLD-2' },
      ] })
      .mockResolvedValueOnce({ holdings: [
        { scheme_code: '120503', folio_number: 'NEW-A' },
        { scheme_code: '120503', folio_number: 'NEW-B' },
      ] });
    const { unmount } = renderDetail('/assets/119288');
    expect(await screen.findByRole('option', { name: 'OLD-1' })).toBeInTheDocument();
    unmount();
    renderDetail('/assets/120503');
    expect(await screen.findByRole('option', { name: 'NEW-A' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'OLD-1' })).not.toBeInTheDocument();
  });

  it('preserves existing query parameters when changing folio', async () => {
    api.fetchAssetDetails
      .mockRejectedValueOnce(new Error('folio_number is required when multiple folios exist for this scheme'))
      .mockResolvedValueOnce({ ...mockAssetDetail, folio_number: 'F/2' });
    api.fetchHoldings.mockResolvedValueOnce({ holdings: [
      { scheme_code: '119288', folio_number: 'F/1' },
      { scheme_code: '119288', folio_number: 'F/2' },
    ] });
    renderDetail('/assets/119288?view=metrics&ref=assets');
    expect(screen.getByTestId('location-search')).toHaveTextContent('?view=metrics&ref=assets');
    const picker = await screen.findByRole('combobox', { name: 'Folio' });
    fireEvent.change(picker, { target: { value: 'F/2' } });
    await screen.findByText('Position / Cost Basis');
    const search = screen.getByTestId('location-search').textContent || '';
    const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
    expect(params.get('folio_number')).toBe('F/2');
    expect(params.get('view')).toBe('metrics');
    expect(params.get('ref')).toBe('assets');
    expect(api.fetchAssetDetails).toHaveBeenLastCalledWith(
      '119288', expect.objectContaining({ portfolio_scope: 'all' }), 'F/2'
    );
  });

  it('loads fund analytics independently when personal position requires a folio', async () => {
    api.fetchAssetDetails.mockRejectedValueOnce(new Error('folio_number is required when multiple folios exist for this scheme'));
    api.getAssetMetricSheet.mockResolvedValueOnce({
      ...mockMetricSheet, performance_basis: 'nav', currency: 'INR',
      coverage: { start: '2024-03-01', end: '2024-04-30', incomplete: true },
      metrics: { return: { cumulative_return: null, cagr: null, twror: null, xirr: null } },
      periodic_returns: { monthly: [{ period: '2024-04', return: 0.0123 }], yearly: [] },
      personal_metrics: { xirr: 0.2876, status: 'calculated', basis: 'native_inr' },
    });
    renderDetail('/assets/118968');
    await screen.findByRole('heading', { name: 'Fund Performance — INR' });
    expect(screen.getByText(/multiple folios/i)).toBeInTheDocument();
    expect(screen.getByText('Actual NAV coverage: 2024-03-01 to 2024-04-30 (Incomplete)')).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: /April 2024.*1.23%/i })).toBeInTheDocument();
    expect(screen.getByText('+28.76%')).toBeInTheDocument();
    expect(screen.getByText('Cumulative NAV Return').closest('.ui-metric-card')).toHaveTextContent('—');
    expect(api.getAssetMetricSheet).toHaveBeenCalledWith('118968', expect.objectContaining({ portfolio_scope: 'all' }));
  });

  it('does not bypass a position authorization error with an analytics request', async () => {
    api.fetchAssetDetails.mockRejectedValueOnce(new Error('Forbidden'));
    renderDetail();
    await screen.findByText('Forbidden');
    expect(api.getAssetMetricSheet).not.toHaveBeenCalled();
  });

  it('renders safely for zero quantity', async () => {
    api.fetchAssetDetails.mockResolvedValueOnce({
      ...mockAssetDetail,
      current_value: 0,
      cumulative_qty: 0,
      cumulative_invested_amount: 0,
      avg_cost_per_share: 0,
      realized_pl: 0,
      unrealized_pl: 0,
      xirr: null,
    });

    renderDetail();

    expect(await screen.findByRole('heading', { name: 'A' })).toBeInTheDocument();
    expect(screen.getAllByText('0.0000').length).toBeGreaterThan(0);
  });

  it('renders transaction history for this asset', async () => {
    api.fetchAssetDetails.mockResolvedValueOnce({
      ...mockAssetDetail,
      current_price: 100,
      current_value: 100,
      cumulative_qty: 1,
      cumulative_invested_amount: 100,
      avg_cost_per_share: 100,
      realized_pl: 0,
      unrealized_pl: 0,
      xirr: null,
      transactions: [
        {
          id: 1,
          asset_symbol: 'A',
          date: '2026-01-02',
          type: 'BUY',
          quantity: 1,
          price_per_share: 100,
          fees: 1,
          currency: 'EUR',
          split_from: null,
          split_to: null,
          conversion_ratio: null,
          needs_review: false,
        },
        {
          id: 2,
          asset_symbol: 'A',
          date: '2026-01-03',
          type: 'STOCK_SPLIT',
          quantity: 0,
          price_per_share: 0,
          fees: 0,
          currency: 'EUR',
          split_from: 1,
          split_to: 2,
          conversion_ratio: null,
          needs_review: false,
        },
      ],
    });

    renderDetail();

    expect(await screen.findByRole('heading', { name: 'A' })).toBeInTheDocument();
    expect(screen.getByText('2026-01-03')).toBeInTheDocument();
    expect(screen.getByText('BUY')).toBeInTheDocument();
    expect(screen.getByText('STOCK_SPLIT')).toBeInTheDocument();
    expect(screen.getByText('1:2')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Transaction History' })).toBeInTheDocument();
  });

  describe('Metric Sheet', () => {
    it('calls getAssetMetricSheet with symbol, scope, range, and currency', async () => {
      api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);

      renderDetail();

      await waitFor(() => {
        expect(api.getAssetMetricSheet).toHaveBeenCalledWith('A', {
          portfolio_scope: 'all',
          display_currency: 'EUR',
          range: '1Y',
        });
      });
    });

    it('renders Metric Sheet metrics after successful fetch', async () => {
      api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);

      renderDetail();

      const section = await waitFor(() => {
        const card = screen.getByRole('heading', { name: 'Metric Sheet' }).closest('.ui-section-card');
        expect(within(card).getByText('Sharpe Ratio')).toBeInTheDocument();
        return card;
      });
      expect(within(section).getByText('+12.34%')).toBeInTheDocument();
    });

    it('renders periodic returns and worst drawdown periods from backend', async () => {
      api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);

      renderDetail();

      const section = await waitFor(() => {
        const card = screen.getByRole('heading', { name: 'Metric Sheet' }).closest('.ui-section-card');
        expect(within(card).getByText('Periodic returns')).toBeInTheDocument();
        expect(within(card).getByText('Calendar-Year Return')).toBeInTheDocument();
        return card;
      });
      expect(within(section).getByText('Worst drawdowns')).toBeInTheDocument();
      expect(
        within(section).getByRole('heading', { name: 'Drawdown', level: 3 })
      ).toBeInTheDocument();
      expect(within(section).getByRole('columnheader', { name: 'Feb' })).toBeInTheDocument();
      expect(within(section).getAllByText('−1.20%').length).toBeGreaterThan(0);
    });

    it('displays backend Metric Sheet warnings', async () => {
      api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);

      renderDetail();

      await waitFor(() => {
        expect(screen.getByText(/split-adjusted/i)).toBeInTheDocument();
      });
    });

    it('shows em dash for null metric values', async () => {
      api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);
      api.getAssetMetricSheet.mockResolvedValueOnce({
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
        warnings: [],
      });

      renderDetail();

      await waitFor(() => {
        const section = screen.getByRole('heading', { name: 'Metric Sheet' }).closest('.ui-section-card');
        expect(within(section).getAllByText('—').length).toBeGreaterThan(0);
      });
    });

    it('refetches when range control changes', async () => {
      api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);

      renderDetail();

      await screen.findByRole('group', { name: 'asset-metric-sheet-range' });
      fireEvent.click(screen.getByRole('button', { name: '30D' }));

      await waitFor(() => {
        expect(api.getAssetMetricSheet).toHaveBeenCalledWith(
          'A',
          expect.objectContaining({ range: '30D' })
        );
      });
    });

    it('passes benchmark param and shows benchmark table when returned', async () => {
      api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);

      renderDetail();

      await waitFor(() => expect(api.getAssetMetricSheet).toHaveBeenCalledTimes(1));

      const benchSel = await screen.findByLabelText('asset-metric-sheet-benchmark');
      fireEvent.change(benchSel, { target: { value: '^GSPC' } });

      await waitFor(() => {
        expect(api.getAssetMetricSheet).toHaveBeenLastCalledWith(
          'A',
          expect.objectContaining({ benchmark: '^GSPC' })
        );
      });

      await waitFor(() => {
        expect(screen.getByText('Beta')).toBeInTheDocument();
      });
    });

    it('Metric Sheet failure does not break Asset Detail content', async () => {
      api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);
      api.getAssetMetricSheet.mockRejectedValueOnce(new Error('Analytics unavailable'));

      renderDetail();

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'A' })).toBeInTheDocument();
        expect(screen.getByText('Position / Cost Basis')).toBeInTheDocument();
        expect(screen.getByText('Metric Sheet unavailable')).toBeInTheDocument();
        expect(screen.getByText('Analytics unavailable')).toBeInTheDocument();
      });
    });

    it('passes folio_number when present on asset detail payload', async () => {
      api.fetchAssetDetails.mockResolvedValueOnce({
        ...mockAssetDetail,
        asset_symbol: '120503',
        asset_type: 'MUTUAL_FUND',
        folio_number: 'FOLIO-12345',
      });

      renderDetail('/assets/120503');

      await waitFor(() => {
        expect(api.getAssetMetricSheet).toHaveBeenCalledWith(
          '120503',
          expect.objectContaining({ folio_number: 'FOLIO-12345' })
        );
      });
    });

    it('shows folio guidance when backend requires folio_number', async () => {
      api.fetchAssetDetails.mockResolvedValueOnce(mockAssetDetail);
      api.getAssetMetricSheet.mockRejectedValueOnce(
        new Error('folio_number is required when multiple folios exist for this scheme')
      );

      renderDetail();

      await waitFor(() => {
        expect(
          screen.getByText("Select a specific folio to view this asset's Metric Sheet.")
        ).toBeInTheDocument();
        expect(screen.getByText('Position / Cost Basis')).toBeInTheDocument();
      });
    });
  });

  it('does not fetch asset details before settings load', async () => {
    let resolveSettings;
    api.getSettings.mockReturnValue(
      new Promise((resolve) => {
        resolveSettings = () => resolve({ display_currency: 'EUR' });
      })
    );
    api.fetchPortfolios.mockResolvedValue([]);
    api.fetchAssetDetails.mockResolvedValue(mockAssetDetail);

    render(
      <PortfolioProvider>
        <MemoryRouter initialEntries={['/assets/A']}>
          <Routes>
            <Route path="/assets/:assetSymbol" element={<AssetDetail />} />
          </Routes>
        </MemoryRouter>
      </PortfolioProvider>
    );

    expect(screen.getByText(/loading display settings/i)).toBeInTheDocument();
    expect(api.fetchAssetDetails).not.toHaveBeenCalled();

    await act(async () => {
      resolveSettings();
    });

    await waitFor(() => {
      expect(api.fetchAssetDetails).toHaveBeenCalledWith('A', {
        portfolio_scope: 'all',
        display_currency: 'EUR',
      });
    });
  });
});
