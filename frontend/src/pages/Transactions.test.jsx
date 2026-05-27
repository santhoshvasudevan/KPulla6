import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Transactions from './Transactions';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', () => ({
  fetchTransactions: vi.fn(),
  createTransaction: vi.fn(),
  updateTransaction: vi.fn(),
  deleteTransaction: vi.fn(),
  importTransactionsCsv: vi.fn(),
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

const mockTransactions = {
  items: [
    { id: 1, asset_symbol: 'AAPL', date: '2026-05-01', type: 'BUY', quantity: 10, price_per_share: 150.00, fees: 2.50, currency: 'EUR', portfolio_id: 1, portfolio_name: 'Default Portfolio' },
  ],
  total: 1,
  page: 1,
  page_size: 20,
  pages: 1,
};

describe('Transactions Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
  });

  it('renders transaction rows after data loads', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchTransactions.mockResolvedValue(mockTransactions);
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText(/€150\.00/)).toBeInTheDocument();
    });
    expect(screen.getAllByText('Default Portfolio').length).toBeGreaterThan(0);
    // Called at least once initially, and again after settings load updates display currency.
    await waitFor(() => {
      expect(api.fetchTransactions).toHaveBeenCalledWith(1, 50, { portfolio_scope: 'all', display_currency: 'USD' });
    });
  });

  it('opens add transaction modal on button click', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchTransactions.mockResolvedValue(mockTransactions);
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });

    const addButton = screen.getByText(/Add Transaction/i);
    fireEvent.click(addButton);

    expect(screen.getByText('Add Transaction', { selector: 'h3' })).toBeInTheDocument();
  });

  it('opens edit modal and pre-fills data', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchTransactions.mockResolvedValue(mockTransactions);
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });

    const editButton = screen.getByTitle('Edit');
    fireEvent.click(editButton);

    expect(screen.getByText('Edit Transaction', { selector: 'h3' })).toBeInTheDocument();
    expect(screen.getByDisplayValue('AAPL')).toBeInTheDocument();
    expect(screen.getByDisplayValue('10')).toBeInTheDocument();
  });

  it('CSV import success shows count and refetches', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchTransactions.mockResolvedValue(mockTransactions);
    api.importTransactionsCsv.mockResolvedValue({ success: true, imported_count: 3, errors: [] });
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    const file = new File(['a'], 't.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]');
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => {
      expect(api.importTransactionsCsv).toHaveBeenCalledWith(file, null);
      expect(screen.getByText('Imported 3 transactions')).toBeInTheDocument();
    });
    expect(api.fetchTransactions.mock.calls.length).toBeGreaterThan(1);
  });

  it('CSV import shows validation errors', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchTransactions.mockResolvedValue(mockTransactions);
    api.importTransactionsCsv.mockResolvedValue({
      success: false,
      imported_count: 0,
      errors: [{ row: 2, field: 'Qty', message: 'Quantity must be positive' }],
    });
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    const file = new File(['a'], 't.csv', { type: 'text/csv' });
    fireEvent.change(document.querySelector('input[type="file"]'), { target: { files: [file] } });
    await waitFor(() => {
      expect(screen.getByText(/Row 2/)).toBeInTheDocument();
      expect(screen.getByText(/Quantity must be positive/)).toBeInTheDocument();
    });
    expect(api.importTransactionsCsv).toHaveBeenCalledWith(file, null);
  });

  it('CSV import uses selected real portfolio id when filtered', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([
      { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
      { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
    ]);
    api.fetchTransactions.mockResolvedValue(mockTransactions);
    api.importTransactionsCsv.mockResolvedValue({ success: true, imported_count: 1, errors: [] });
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });

    render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
          { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
        ]}
        initialSelection={{ mode: 'portfolio', id: 2, name: 'P2' }}
        disableFetch
      >
        <Transactions />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(api.fetchTransactions).toHaveBeenCalledWith(1, 50, { portfolio_id: 2, display_currency: 'EUR' });
    });

    const file = new File(['a'], 't.csv', { type: 'text/csv' });
    fireEvent.change(document.querySelector('input[type="file"]'), { target: { files: [file] } });
    await waitFor(() => {
      expect(api.importTransactionsCsv).toHaveBeenCalledWith(file, 2);
    });
  });

  it('calls delete API and reloads data on delete button click', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchTransactions.mockResolvedValue(mockTransactions);
    api.fetchTransactions.mockResolvedValueOnce({ items: [], total: 0 });
    api.deleteTransaction.mockResolvedValueOnce({});
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTitle('Delete'));
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(api.deleteTransaction).toHaveBeenCalledWith(1);
      expect(api.fetchTransactions).toHaveBeenCalledTimes(2);
    });
  });

  it('shows bulk toolbar when rows are selected', async () => {
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchTransactions.mockResolvedValue({
      items: [
        { id: 1, asset_symbol: 'AAPL', date: '2026-05-01', type: 'BUY', quantity: 10, price_per_share: 150, fees: 2.5, currency: 'EUR', portfolio_id: 1, portfolio_name: 'Default Portfolio' },
        { id: 2, asset_symbol: 'MSFT', date: '2026-05-02', type: 'BUY', quantity: 5, price_per_share: 300, fees: 0, currency: 'EUR', portfolio_id: 1, portfolio_name: 'Default Portfolio' },
      ],
      total: 2,
    });
    render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
          { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
        ]}
        disableFetch
      >
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    expect(screen.queryByLabelText('Bulk actions')).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Select transaction 1'));
    expect(screen.getByLabelText('Bulk actions')).toBeInTheDocument();
    expect(screen.getByText('1 selected')).toBeInTheDocument();
  });

  it('assigns selected transactions with full payload and new portfolio_id', async () => {
    const txn1 = { id: 1, asset_symbol: 'AAPL', date: '2026-05-01', type: 'BUY', quantity: 10, price_per_share: 150, fees: 2.5, currency: 'EUR', portfolio_id: 1, portfolio_name: 'Default Portfolio' };
    const txn2 = { id: 2, asset_symbol: 'MSFT', date: '2026-05-02', type: 'BUY', quantity: 5, price_per_share: 300, fees: 0, currency: 'EUR', portfolio_id: 1, portfolio_name: 'Default Portfolio' };
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchTransactions.mockResolvedValue({ items: [txn1, txn2], total: 2 });
    api.updateTransaction.mockResolvedValue({});
    render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
          { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
        ]}
        disableFetch
      >
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByLabelText('Select transaction 1'));
    fireEvent.click(screen.getByLabelText('Select transaction 2'));
    fireEvent.change(screen.getByLabelText('assign to portfolio'), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() => {
      expect(api.updateTransaction).toHaveBeenCalledTimes(2);
      expect(api.updateTransaction).toHaveBeenCalledWith(1, expect.objectContaining({
        asset_symbol: 'AAPL',
        portfolio_id: 2,
        quantity: 10,
        price_per_share: 150,
      }));
      expect(api.updateTransaction).toHaveBeenCalledWith(2, expect.objectContaining({
        asset_symbol: 'MSFT',
        portfolio_id: 2,
      }));
    });
    await waitFor(() => {
      expect(screen.getByText(/assigned 2 transactions successfully/i)).toBeInTheDocument();
    });
    expect(screen.queryByText('2 selected')).not.toBeInTheDocument();
  });

  it('preserves STOCK_SPLIT fields on bulk reassignment', async () => {
    const splitTxn = {
      id: 10,
      asset_symbol: 'GOOG',
      date: '2022-07-15',
      type: 'STOCK_SPLIT',
      quantity: 0,
      price_per_share: 0,
      currency: 'EUR',
      fees: 0,
      split_from: 1,
      split_to: 20,
      portfolio_id: 1,
      portfolio_name: 'Default Portfolio',
    };
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchTransactions.mockResolvedValue({ items: [splitTxn], total: 1 });
    api.updateTransaction.mockResolvedValue({});
    render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
          { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
        ]}
        disableFetch
      >
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('GOOG')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByLabelText('Select transaction 10'));
    fireEvent.change(screen.getByLabelText('assign to portfolio'), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() => {
      expect(api.updateTransaction).toHaveBeenCalledWith(10, expect.objectContaining({
        type: 'STOCK_SPLIT',
        split_from: 1,
        split_to: 20,
        portfolio_id: 2,
      }));
    });
  });

  it('shows partial failure warning when bulk assign fails for some rows', async () => {
    const txn1 = { id: 1, asset_symbol: 'AAPL', date: '2026-05-01', type: 'BUY', quantity: 10, price_per_share: 150, fees: 2.5, currency: 'EUR', portfolio_id: 1, portfolio_name: 'Default Portfolio' };
    const txn2 = { id: 2, asset_symbol: 'MSFT', date: '2026-05-02', type: 'BUY', quantity: 5, price_per_share: 300, fees: 0, currency: 'EUR', portfolio_id: 1, portfolio_name: 'Default Portfolio' };
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchTransactions.mockResolvedValue({ items: [txn1, txn2], total: 2 });
    api.updateTransaction
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new Error('Validation failed'));
    render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
          { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
        ]}
        disableFetch
      >
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByLabelText('Select all transactions on this page'));
    fireEvent.change(screen.getByLabelText('assign to portfolio'), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() => {
      expect(screen.getByText(/1 succeeded, 1 failed/i)).toBeInTheDocument();
      expect(screen.getByText(/validation failed/i)).toBeInTheDocument();
    });
  });

  it('renders mutual fund rows with scheme, folio, and NAV status', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    api.fetchTransactions.mockResolvedValue({
      items: [
        { id: 1, asset_symbol: 'AAPL', date: '2026-05-01', type: 'BUY', quantity: 10, price_per_share: 150, fees: 2.5, currency: 'EUR', portfolio_id: 1, portfolio_name: 'Default Portfolio' },
        {
          id: 2,
          asset_type: 'MUTUAL_FUND',
          asset_symbol: '120503',
          scheme_code: '120503',
          scheme_name: 'Test Direct Growth Fund',
          folio_number: 'FOLIO-12345',
          date: '2026-03-15',
          nav_date: '2026-03-15',
          type: 'BUY',
          units_allotted: 100,
          nav: 42.5,
          quantity: 100,
          price_per_share: 42.5,
          paid_value: 4255,
          market_value: 4250,
          fees: 5,
          currency: 'INR',
          portfolio_id: 1,
          portfolio_name: 'Default Portfolio',
          nav_verification_status: 'VERIFIED',
        },
      ],
      total: 2,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText(/Test Direct Growth Fund/)).toBeInTheDocument();
      expect(screen.getByText(/Folio FOLIO-12345/)).toBeInTheDocument();
      expect(screen.getByText('NAV verified')).toBeInTheDocument();
    });
  });
});
