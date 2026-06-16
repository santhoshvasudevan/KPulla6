import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Assets from './Assets';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', () => ({
  fetchHoldings: vi.fn(),
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div data-testid="chart-container">{children}</div>,
  PieChart: ({ children }) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => <div data-testid="pie" />,
  Tooltip: () => null,
  Legend: () => null,
  Cell: () => null,
}));

const mockSummary = {
  fx_status: 'ok',
  holdings: [
    {
      asset_symbol: 'AAPL',
      quantity: 10,
      currency: 'EUR',
      invested: 1500,
      avg_cost_per_share: 150,
      current_price: 175.5,
      current_value: 1755,
      unrealized_pl: 255,
      xirr: 0.125,
      price_status: 'ok',
    },
    {
      asset_symbol: 'MSFT',
      quantity: 0,
      currency: 'EUR',
      invested: 10,
      current_price: 10,
      current_value: 10,
      unrealized_pl: 0,
      xirr: null,
      realized_pl: 5,
    }
  ]
};

function renderAssets() {
  return render(
    <PortfolioProvider>
      <MemoryRouter initialEntries={['/assets']}>
        <Routes>
          <Route path="/assets" element={<Assets />} />
          <Route path="/assets/:assetSymbol" element={<div data-testid="asset-detail-route" />} />
        </Routes>
      </MemoryRouter>
    </PortfolioProvider>
  );
}

describe('Assets Page', () => {
  it('shows a loading state initially', () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchHoldings.mockReturnValueOnce(new Promise(() => {}));
    renderAssets();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders the assets table and allocation chart', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchHoldings.mockResolvedValue(mockSummary);
    renderAssets();

    await waitFor(() => {
      expect(screen.getByText('Assets Overview')).toBeInTheDocument();
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.queryByText('MSFT')).not.toBeInTheDocument();
      expect(screen.getByText('10.0000')).toBeInTheDocument();
      expect(screen.getByText(/€150\.00/)).toBeInTheDocument();
      expect(screen.getByText(/175\.50/)).toBeInTheDocument();
      expect(screen.getByText('12.50%')).toBeInTheDocument();
      expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(api.fetchHoldings).toHaveBeenCalledWith({ portfolio_scope: 'all', display_currency: 'EUR' });
    });

    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('AAPL');

    fireEvent.click(screen.getByText('Symbol'));
    const rowsAfter = screen.getAllByRole('row');
    expect(rowsAfter[1]).toHaveTextContent('AAPL');

    fireEvent.click(screen.getByText('AAPL'));
    expect(await screen.findByTestId('asset-detail-route')).toBeInTheDocument();
  });

  it('previous holdings is collapsed initially and can be expanded', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchHoldings.mockResolvedValue(mockSummary);
    renderAssets();

    expect(await screen.findByText('Assets Overview')).toBeInTheDocument();
    expect(screen.getByText('Show previous holdings')).toBeInTheDocument();
    expect(screen.queryByText('MSFT')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Show previous holdings'));
    expect(await screen.findByText('Hide previous holdings')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('shows chart empty state when all current values are zero', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchHoldings.mockResolvedValue({
      fx_status: 'ok',
      holdings: [
        {
          asset_symbol: 'X',
          quantity: 5,
          currency: 'EUR',
          invested: 100,
          current_price: null,
          current_value: 0,
          unrealized_pl: -100,
          price_status: 'price_missing',
        },
      ],
    });
    renderAssets();
    await waitFor(() => {
      expect(screen.getByText(/Allocation chart unavailable until latest prices are synced/i)).toBeInTheDocument();
    });
    expect(screen.queryByTestId('pie-chart')).not.toBeInTheDocument();
  });

  it('shows price missing message without fetching wording', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchHoldings.mockResolvedValue({
      fx_status: 'ok',
      holdings: [
        {
          asset_symbol: 'X',
          quantity: 1,
          invested: 10,
          current_price: null,
          current_value: 0,
          unrealized_pl: 0,
          price_status: 'price_missing',
        },
      ],
    });
    renderAssets();
    await waitFor(() => {
      expect(screen.getByText(/Price missing — run refresh to fetch latest price/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Fetching latest price/i)).not.toBeInTheDocument();
  });

  it('shows FX warning only when conversion is actually needed', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchHoldings.mockResolvedValue({
      fx_status: 'fx_unavailable',
      holdings: [
        {
          asset_symbol: 'AAPL',
          quantity: 10,
          currency: 'EUR',
          invested: 1000,
          current_price: 120,
          current_value: 1200,
          unrealized_pl: 200,
          price_status: 'ok',
        },
      ],
    });
    renderAssets();
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    expect(screen.queryByText(/FX unavailable/i)).not.toBeInTheDocument();
  });

  it('shows FX warning when display currency differs from holdings', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchHoldings.mockResolvedValue({
      fx_status: 'fx_unavailable',
      holdings: [
        {
          asset_symbol: 'AAPL',
          quantity: 10,
          currency: 'EUR',
          invested: 1000,
          current_price: 120,
          current_value: 1200,
          unrealized_pl: 200,
          price_status: 'ok',
        },
      ],
    });
    renderAssets();
    await waitFor(() => {
      expect(screen.getByText(/FX unavailable for display currency conversion/i)).toBeInTheDocument();
    });
  });

  it('shows oversold status without breaking the page', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchHoldings.mockResolvedValue({
      fx_status: 'ok',
      holdings: [
        {
          asset_symbol: 'BAD',
          quantity: 2,
          currency: 'EUR',
          invested: 0,
          current_price: 10,
          current_value: 20,
          unrealized_pl: 0,
          price_status: 'ok',
          holding_status: 'oversold',
          warnings: ['SELL quantity exceeded available FIFO lots for this asset'],
        },
        {
          asset_symbol: 'GOOD',
          quantity: 5,
          currency: 'EUR',
          invested: 500,
          current_price: 120,
          current_value: 600,
          unrealized_pl: 100,
          price_status: 'ok',
        },
      ],
    });
    renderAssets();
    await waitFor(() => {
      expect(screen.getByText('Oversold')).toBeInTheDocument();
      expect(screen.getByText('GOOD')).toBeInTheDocument();
    });
  });

  it('shows cash balances section and excludes cash from holdings table', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchHoldings.mockResolvedValue({
      fx_status: 'ok',
      holdings: [
        {
          asset_symbol: 'AAPL',
          quantity: 10,
          currency: 'EUR',
          invested: 1500,
          current_price: 175.5,
          current_value: 1755,
          unrealized_pl: 255,
          price_status: 'ok',
          holding_status: 'ok',
        },
      ],
      allocation: [
        {
          asset_symbol: 'AAPL',
          quantity: 10,
          currency: 'EUR',
          current_value: 1755,
          holding_status: 'ok',
        },
        {
          asset_type: 'CASH',
          asset_symbol: 'Cash EUR',
          primary_asset_class: 'CASH',
          currency: 'EUR',
          native_currency: 'EUR',
          native_balance: 1200,
          current_value: 1200,
          is_cash: true,
          holding_status: 'ok',
        },
        {
          asset_type: 'CASH',
          asset_symbol: 'Cash USD',
          primary_asset_class: 'CASH',
          currency: 'EUR',
          native_currency: 'USD',
          native_balance: 500,
          current_value: 460,
          is_cash: true,
          holding_status: 'ok',
        },
      ],
    });
    renderAssets();
    await waitFor(() => {
      expect(screen.getByText('Cash balances')).toBeInTheDocument();
      expect(screen.getByText('Cash EUR')).toBeInTheDocument();
      expect(screen.getByText('Cash USD')).toBeInTheDocument();
      expect(screen.getAllByText(/€1,200\.00/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/\$500\.00/)).toBeInTheDocument();
      expect(screen.getByText(/€460\.00/)).toBeInTheDocument();
      expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
    });

    const cashRow = screen.getByText('Cash EUR').closest('tr');
    expect(cashRow).not.toHaveClass('assets-table__row-clickable');
    fireEvent.click(screen.getByText('Cash EUR'));
    expect(screen.queryByTestId('asset-detail-route')).not.toBeInTheDocument();
  });

  it('renders bank cash rows without quantity or price fields', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'INR' });
    api.fetchHoldings.mockResolvedValueOnce({
      fx_status: 'ok',
      holdings: [
        {
          asset_type: 'BANK_CASH',
          holding_key: 'bank:1',
          bank_account_name: 'Savings',
          asset_symbol: 'Savings',
          institution_name: 'HDFC',
          account_number: '123456',
          currency: 'INR',
          current_value: 25000,
          invested_amount: 25000,
          holding_status: 'ok',
          unrealized_pl: 0,
        },
        {
          asset_type: 'FIXED_DEPOSIT',
          holding_key: 'fd:1',
          institution_name: 'HDFC',
          deposit_account_number: 'FD-001',
          asset_symbol: 'FD HDFC',
          currency: 'INR',
          principal_amount: 100000,
          current_value: 100000,
          value_status: 'principal_only',
          holding_status: 'ok',
        },
      ],
      allocation: [],
    });
    renderAssets();
    await waitFor(() => {
      expect(screen.getByText('Savings')).toBeInTheDocument();
      expect(screen.getByText('Bank Cash')).toBeInTheDocument();
      expect(screen.getByText(/HDFC · 123456/)).toBeInTheDocument();
      expect(screen.getByText(/HDFC \(FD-001\)/)).toBeInTheDocument();
      expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3);
    });
  });

  it('renders fixed deposit rows without price or quantity warnings', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'INR' });
    api.fetchHoldings.mockResolvedValueOnce({
      fx_status: 'ok',
      holdings: [
        {
          asset_type: 'FIXED_DEPOSIT',
          holding_key: 'fd:1',
          institution_name: 'HDFC',
          deposit_account_number: 'FD-001',
          asset_symbol: 'FD HDFC',
          currency: 'INR',
          principal_amount: 100000,
          current_value: 100000,
          value_status: 'principal_only',
          holding_status: 'ok',
          maturity_date: '2026-01-01',
          status: 'ACTIVE',
        },
      ],
      allocation: [],
    });
    renderAssets();
    await waitFor(() => {
      expect(screen.getByText(/HDFC \(FD-001\)/)).toBeInTheDocument();
      expect(screen.getByText('Fixed Deposit')).toBeInTheDocument();
      expect(screen.getByText(/Matures 2026-01-01/)).toBeInTheDocument();
      expect(screen.queryByText(/price unavailable/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/price missing/i)).not.toBeInTheDocument();
      expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3);
    });
  });

  it('shows empty state when no assets', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchHoldings.mockResolvedValueOnce({ holdings: [] });
    renderAssets();

    await waitFor(() => {
      expect(screen.getByText(/no assets found/i)).toBeInTheDocument();
    });
  });
});
