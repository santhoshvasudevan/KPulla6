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
    api.fetchTransactions.mockResolvedValueOnce({ items: [], total: 0 }); // after delete
    api.deleteTransaction.mockResolvedValueOnce({});
    
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });

    const deleteButton = screen.getByTitle('Delete');
    fireEvent.click(deleteButton);

    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(api.deleteTransaction).toHaveBeenCalledWith(1);
      expect(api.fetchTransactions).toHaveBeenCalledTimes(2);
    });
  });
});
