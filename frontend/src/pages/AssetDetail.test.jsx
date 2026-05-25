import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AssetDetail from './AssetDetail';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', () => ({
  fetchAssetDetails: vi.fn(),
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

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
  it('renders returned metrics', async () => {
    api.fetchAssetDetails.mockResolvedValueOnce({
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
    });

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
      expect(screen.getByText('+12.50%')).toBeInTheDocument();
    });
  });

  it('renders safely for zero quantity', async () => {
    api.fetchAssetDetails.mockResolvedValueOnce({
      asset_symbol: 'A',
      currency: 'EUR',
      current_price: 100,
      current_value: 0,
      cumulative_qty: 0,
      cumulative_invested_amount: 0,
      avg_cost_per_share: 0,
      realized_pl: 0,
      unrealized_pl: 0,
      xirr: null,
      transactions: [],
    });

    renderDetail();

    expect(await screen.findByRole('heading', { name: 'A' })).toBeInTheDocument();
    expect(screen.getAllByText('0.0000').length).toBeGreaterThan(0);
  });

  it('renders transaction history for this asset', async () => {
    api.fetchAssetDetails.mockResolvedValueOnce({
      asset_symbol: 'A',
      currency: 'EUR',
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
});

