import { render, screen, waitFor, fireEvent, within, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AssetDetail from './AssetDetail';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';
import samplePortfolioMetricSheetPayload from '../components/metricSheet/fixtures/samplePortfolioMetricSheetPayload';

vi.mock('../api', () => ({
  fetchAssetDetails: vi.fn(),
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
        return card;
      });
      expect(within(section).getByText('Worst drawdowns')).toBeInTheDocument();
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
