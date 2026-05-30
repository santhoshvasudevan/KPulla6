import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Transactions from './Transactions';
import * as api from '../api';
import { PortfolioProvider, usePortfolio } from '../portfolioContext';
import * as csvGuidance from '../utils/csvImportGuidance';

vi.mock('../api', () => ({
  fetchTransactions: vi.fn(),
  fetchTransactionFilterOptions: vi.fn(),
  createTransaction: vi.fn(),
  updateTransaction: vi.fn(),
  deleteTransaction: vi.fn(),
  importTransactionsCsv: vi.fn(),
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

const NO_FILTERS = { symbols: [], date_from: null, date_to: null };

const mockTxn = {
  id: 1,
  asset_symbol: 'AAPL',
  date: '2026-05-01',
  type: 'BUY',
  quantity: 10,
  price_per_share: 150.0,
  fees: 2.5,
  currency: 'EUR',
  portfolio_id: 1,
  portfolio_name: 'Default Portfolio',
};

const mockTransactions = {
  items: [mockTxn],
  total: 1,
  page: 1,
  page_size: 50,
  pages: 1,
};

function makePagedResponse({ page = 1, pageSize = 50, total = 75, pages = 2 } = {}) {
  const items = Array.from({ length: Math.min(pageSize, total - (page - 1) * pageSize) }, (_, i) => ({
    ...mockTxn,
    id: (page - 1) * pageSize + i + 1,
    asset_symbol: page === 1 && i === 0 ? 'AAPL' : `SYM-${(page - 1) * pageSize + i + 1}`,
  }));
  return { items, total, page, page_size: pageSize, pages };
}

function mockPagedTransactions() {
  api.fetchTransactions.mockImplementation((page) =>
    Promise.resolve(makePagedResponse({ page }))
  );
}

describe('Transactions Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
    api.fetchTransactionFilterOptions.mockResolvedValue({ portfolios: [], symbols: [] });
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
      expect(api.fetchTransactions).toHaveBeenCalledWith(
        1,
        50,
        { portfolio_scope: 'all', display_currency: 'USD' },
        NO_FILTERS
      );
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

  it('shows stock and mutual fund CSV import guidance', async () => {
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
    expect(screen.getByText('Supported CSV formats')).toBeInTheDocument();
    expect(screen.getByText('Stock CSV')).toBeInTheDocument();
    expect(screen.getByText('Mutual fund CSV')).toBeInTheDocument();
    expect(screen.getByText(/ASSET SYMBOL/)).toBeInTheDocument();
    expect(screen.getAllByText(/Scheme Code/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Do not mix stock and mutual fund rows/i)).toBeInTheDocument();
    expect(screen.getByText(/MF dates must be MM\/DD\/YY/i)).toBeInTheDocument();
    expect(screen.getByText(/MF Currency defaults to INR/i)).toBeInTheDocument();
    expect(screen.getByText(/SWAP rows import as splits/i)).toBeInTheDocument();
  });

  it('download sample MF CSV button triggers client-side download', async () => {
    const downloadSpy = vi.spyOn(csvGuidance, 'downloadSampleMutualFundCsv').mockImplementation(() => {});
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
    fireEvent.click(screen.getByRole('button', { name: 'Download sample MF CSV' }));
    expect(downloadSpy).toHaveBeenCalledTimes(1);
    downloadSpy.mockRestore();
  });

  it('Import from CSV button still opens file picker flow', async () => {
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
    const input = document.querySelector('input[type="file"]');
    const clickSpy = vi.spyOn(input, 'click');
    fireEvent.click(screen.getByRole('button', { name: 'Import from CSV' }));
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it('renders pagination when total exceeds page_size', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    mockPagedTransactions();
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Transactions pagination')).toBeInTheDocument();
    expect(screen.getByText(/Page 1 of 2/)).toBeInTheDocument();
    expect(screen.getByText(/Showing 1–50 of 75/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next page' })).toBeEnabled();
  });

  it('Next page button fetches page 2', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    mockPagedTransactions();
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    await waitFor(() => {
      expect(api.fetchTransactions).toHaveBeenLastCalledWith(
        2,
        50,
        {
          portfolio_scope: 'all',
          display_currency: 'USD',
        },
        NO_FILTERS
      );
    });
  });

  it('Previous page button fetches page 1 after navigating forward', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    mockPagedTransactions();
    render(
      <PortfolioProvider>
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    await waitFor(() => {
      expect(api.fetchTransactions).toHaveBeenLastCalledWith(2, 50, expect.any(Object), expect.any(Object));
    });
    fireEvent.click(screen.getByRole('button', { name: 'Previous page' }));
    await waitFor(() => {
      expect(api.fetchTransactions).toHaveBeenLastCalledWith(1, 50, expect.any(Object), expect.any(Object));
    });
  });

  it('resets to page 1 when portfolio scope changes', async () => {
    api.getSettings.mockResolvedValueOnce({ display_currency: 'USD' });
    mockPagedTransactions();

    function ScopeSwitcher() {
      const { selectPortfolio } = usePortfolio();
      return (
        <button type="button" onClick={() => selectPortfolio(2, 'P2')}>
          Switch to P2
        </button>
      );
    }

    render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
          { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
        ]}
        disableFetch
      >
        <ScopeSwitcher />
        <Transactions />
      </PortfolioProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    await waitFor(() => {
      expect(api.fetchTransactions).toHaveBeenLastCalledWith(
        2,
        50,
        expect.objectContaining({ portfolio_scope: 'all' }),
        expect.any(Object)
      );
    });

    fireEvent.click(screen.getByRole('button', { name: 'Switch to P2' }));
    await waitFor(() => {
      expect(api.fetchTransactions).toHaveBeenLastCalledWith(
        1,
        50,
        expect.objectContaining({ portfolio_id: 2 }),
        expect.any(Object)
      );
    });
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
    const lastFetch = api.fetchTransactions.mock.calls[api.fetchTransactions.mock.calls.length - 1];
    expect(lastFetch[0]).toBe(1);
    expect(lastFetch[1]).toBe(50);
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
      expect(api.fetchTransactions).toHaveBeenCalledWith(
        1,
        50,
        { portfolio_id: 2, display_currency: 'EUR' },
        NO_FILTERS
      );
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

  describe('Column filters', () => {
    function renderWithFilters() {
      return render(
        <PortfolioProvider
          initialPortfolios={[
            { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
            { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
          ]}
          initialDisplayCurrency="EUR"
          disableFetch
        >
          <Transactions />
        </PortfolioProvider>
      );
    }

    beforeEach(() => {
      api.fetchTransactions.mockResolvedValue(mockTransactions);
      api.fetchTransactionFilterOptions.mockResolvedValue({
        portfolios: [
          { id: 1, name: 'Default Portfolio' },
          { id: 2, name: 'P2' },
        ],
        symbols: ['AAPL', 'MSFT', '120503'],
      });
    });

    it('renders filter controls', async () => {
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      expect(screen.getByLabelText('Filter by portfolio')).toBeInTheDocument();
      expect(screen.getByLabelText('Filter by symbol')).toBeInTheDocument();
      expect(screen.getByLabelText('Date filter mode')).toBeInTheDocument();
    });

    it('selecting a portfolio filter calls API with portfolio_id and resets to page 1', async () => {
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      fireEvent.change(screen.getByLabelText('Filter by portfolio'), { target: { value: '2' } });
      await waitFor(() => {
        expect(api.fetchTransactions).toHaveBeenLastCalledWith(
          1,
          50,
          expect.objectContaining({ portfolio_id: 2 }),
          NO_FILTERS
        );
      });
    });

    it('selecting a symbol filter calls API with symbols', async () => {
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      fireEvent.click(screen.getByLabelText('Filter by symbol'));
      fireEvent.click(screen.getByRole('checkbox', { name: 'MSFT' }));
      await waitFor(() => {
        expect(api.fetchTransactions).toHaveBeenLastCalledWith(
          1,
          50,
          expect.any(Object),
          expect.objectContaining({ symbols: ['MSFT'] })
        );
      });
    });

    it('searching narrows the symbol option list', async () => {
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      fireEvent.click(screen.getByLabelText('Filter by symbol'));
      fireEvent.change(screen.getByLabelText('Search symbols'), { target: { value: 'ms' } });
      expect(screen.getByRole('checkbox', { name: 'MSFT' })).toBeInTheDocument();
      expect(screen.queryByRole('checkbox', { name: 'AAPL' })).not.toBeInTheDocument();
    });

    it('earlier than date sends date_to', async () => {
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      fireEvent.change(screen.getByLabelText('Date filter mode'), { target: { value: 'before' } });
      fireEvent.change(screen.getByLabelText('Date value'), { target: { value: '2026-03-01' } });
      await waitFor(() => {
        expect(api.fetchTransactions).toHaveBeenLastCalledWith(
          1,
          50,
          expect.any(Object),
          expect.objectContaining({ date_from: null, date_to: '2026-03-01' })
        );
      });
    });

    it('later than date sends date_from', async () => {
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      fireEvent.change(screen.getByLabelText('Date filter mode'), { target: { value: 'after' } });
      fireEvent.change(screen.getByLabelText('Date value'), { target: { value: '2026-03-01' } });
      await waitFor(() => {
        expect(api.fetchTransactions).toHaveBeenLastCalledWith(
          1,
          50,
          expect.any(Object),
          expect.objectContaining({ date_from: '2026-03-01', date_to: null })
        );
      });
    });

    it('between dates sends date_from and date_to', async () => {
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      fireEvent.change(screen.getByLabelText('Date filter mode'), { target: { value: 'between' } });
      fireEvent.change(screen.getByLabelText('Date from'), { target: { value: '2026-01-01' } });
      fireEvent.change(screen.getByLabelText('Date to'), { target: { value: '2026-06-01' } });
      await waitFor(() => {
        expect(api.fetchTransactions).toHaveBeenLastCalledWith(
          1,
          50,
          expect.any(Object),
          expect.objectContaining({ date_from: '2026-01-01', date_to: '2026-06-01' })
        );
      });
    });

    it('does not call API when between range is invalid (from > to)', async () => {
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      fireEvent.change(screen.getByLabelText('Date filter mode'), { target: { value: 'between' } });
      fireEvent.change(screen.getByLabelText('Date from'), { target: { value: '2026-06-01' } });
      fireEvent.change(screen.getByLabelText('Date to'), { target: { value: '2026-01-01' } });
      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });
      const invalidCall = api.fetchTransactions.mock.calls.some(
        (c) => c[3]?.date_from === '2026-06-01' && c[3]?.date_to === '2026-01-01'
      );
      expect(invalidCall).toBe(false);
    });

    it('pagination preserves active filters', async () => {
      api.fetchTransactions.mockImplementation((page) =>
        Promise.resolve(makePagedResponse({ page }))
      );
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      fireEvent.click(screen.getByLabelText('Filter by symbol'));
      fireEvent.click(screen.getByRole('checkbox', { name: 'AAPL' }));
      await waitFor(() => {
        expect(api.fetchTransactions).toHaveBeenLastCalledWith(
          1,
          50,
          expect.any(Object),
          expect.objectContaining({ symbols: ['AAPL'] })
        );
      });
      fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
      await waitFor(() => {
        expect(api.fetchTransactions).toHaveBeenLastCalledWith(
          2,
          50,
          expect.any(Object),
          expect.objectContaining({ symbols: ['AAPL'] })
        );
      });
    });

    it('Clear filters resets all filters and refetches', async () => {
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      fireEvent.change(screen.getByLabelText('Filter by portfolio'), { target: { value: '2' } });
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Clear filters' })).toBeInTheDocument();
      });
      fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
      await waitFor(() => {
        expect(api.fetchTransactions).toHaveBeenLastCalledWith(
          1,
          50,
          expect.objectContaining({ portfolio_scope: 'all' }),
          NO_FILTERS
        );
      });
      expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument();
    });

    it('shows active filter chips', async () => {
      renderWithFilters();
      await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
      fireEvent.click(screen.getByLabelText('Filter by symbol'));
      fireEvent.click(screen.getByRole('checkbox', { name: 'MSFT' }));
      await waitFor(() => {
        expect(screen.getByLabelText('Active filters')).toBeInTheDocument();
        expect(screen.getByLabelText('Remove symbol MSFT')).toBeInTheDocument();
      });
    });
  });
});
