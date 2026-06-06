import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Cash from './Cash';
import App from '../App';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';
import { CashApiError } from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    fetchCashBalances: vi.fn(),
    fetchCashLedger: vi.fn(),
    createCashDeposit: vi.fn(),
    createCashWithdrawal: vi.fn(),
    createCashTransfer: vi.fn(),
    updateCashLedgerEntry: vi.fn(),
    deleteCashLedgerEntry: vi.fn(),
    previewCashBulkEntries: vi.fn(),
    applyCashBulkEntries: vi.fn(),
    fetchPortfolios: vi.fn(),
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    invalidateDashboardSummaryCache: vi.fn(),
    ensureCsrfCookie: vi.fn(),
    fetchCurrentUser: vi.fn().mockResolvedValue({ id: 1, username: 'demo', email: 'demo@example.com' }),
    logout: vi.fn(),
    setUnauthorizedHandler: vi.fn(),
    fetchDashboardSummary: vi.fn().mockResolvedValue({
      total_invested: 0,
      current_value: 0,
      realized_pl: 0,
      unrealized_pl: 0,
      total_pl: 0,
      xirr: null,
      display_currency: 'EUR',
      fx_status: 'ok',
    }),
    fetchPortfolioPerformance: vi.fn().mockResolvedValue([]),
    fetchBenchmarkIndices: vi.fn().mockResolvedValue([]),
    getPortfolioMetricSheet: vi.fn().mockResolvedValue({ metrics: {}, warnings: [] }),
  };
});

const mockAuth = {
  user: { id: 1, username: 'demo', email: 'demo@example.com' },
  loading: false,
  isAuthenticated: true,
  login: vi.fn(),
  logout: vi.fn(),
  register: vi.fn(),
  refreshUser: vi.fn(),
};

vi.mock('../authContext', () => ({
  AuthProvider: ({ children }) => children,
  useAuth: () => mockAuth,
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    BrowserRouter: ({ children }) => children,
  };
});

const allBalancesFixture = {
  portfolio_scope: 'all',
  as_of_date: '2026-06-04',
  balances: [
    { portfolio_id: 1, portfolio_name: 'Scalablefolio', currency: 'EUR', balance: 12500 },
    { portfolio_id: 2, portfolio_name: 'IndianMF', currency: 'INR', balance: 50000 },
  ],
  totals_by_currency: [
    { currency: 'EUR', balance: 12500 },
    { currency: 'INR', balance: 50000 },
  ],
};

const emptyBalancesFixture = {
  portfolio_scope: 'all',
  as_of_date: '2026-06-04',
  balances: [],
  totals_by_currency: [],
};

const ledgerFixture = {
  items: [
    {
      id: 10,
      portfolio_id: 1,
      portfolio_name: 'Scalablefolio',
      date: '2026-06-01',
      currency: 'EUR',
      entry_type: 'CASH_DEPOSIT',
      amount: 12500,
      source_of_funds: 'Bank',
      note: 'Seed',
    },
    {
      id: 11,
      portfolio_id: 2,
      portfolio_name: 'IndianMF',
      date: '2026-05-15',
      currency: 'INR',
      entry_type: 'CASH_WITHDRAWAL',
      amount: -1000,
      source_of_funds: null,
      note: null,
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
  pages: 1,
};

const activePortfolios = [
  { id: 1, name: 'Scalablefolio', is_active: true, base_currency: 'EUR' },
  { id: 2, name: 'IndianMF', is_active: true, base_currency: 'INR' },
];

const bulkPreviewFixture = {
  portfolio_id: 1,
  portfolio_name: 'Scalablefolio',
  entry_count: 7,
  entries: [
    {
      date: '2022-06-01',
      currency: 'EUR',
      entry_type: 'CASH_DEPOSIT',
      amount: 900,
      source_of_funds: 'Monthly contribution',
      note: 'Historical contribution',
    },
    {
      date: '2022-07-01',
      currency: 'EUR',
      entry_type: 'CASH_DEPOSIT',
      amount: 900,
      source_of_funds: 'Monthly contribution',
      note: 'Historical contribution',
    },
  ],
  total_by_currency: [{ currency: 'EUR', amount: 6300 }],
  warnings: [],
  duplicate_count: 0,
};

const bulkApplyFixture = {
  portfolio_id: 1,
  portfolio_name: 'Scalablefolio',
  created_count: 7,
  skipped_existing_count: 0,
  created_entries: [
    {
      id: 301,
      date: '2022-06-01',
      currency: 'EUR',
      entry_type: 'CASH_DEPOSIT',
      amount: 900,
      source_of_funds: 'Monthly contribution',
      note: 'Historical contribution',
    },
  ],
  total_by_currency: [{ currency: 'EUR', amount: 6300 }],
};

function renderCash(options = {}) {
  const { initialSelection, initialPortfolios = activePortfolios } = options;
  return render(
    <PortfolioProvider
      disableFetch
      initialPortfolios={initialPortfolios}
      initialSelection={initialSelection}
      initialDisplayCurrency="EUR"
    >
      <Cash />
    </PortfolioProvider>
  );
}

describe('Cash page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchCashBalances.mockResolvedValue(allBalancesFixture);
    api.fetchCashLedger.mockResolvedValue(ledgerFixture);
    api.createCashDeposit.mockResolvedValue({ id: 99 });
    api.createCashWithdrawal.mockResolvedValue({ id: 100 });
    api.createCashTransfer.mockResolvedValue({
      transfer_group_id: 10,
      entries: [{ id: 201, entry_type: 'TRANSFER_OUT' }, { id: 202, entry_type: 'TRANSFER_IN' }],
    });
    api.updateCashLedgerEntry.mockResolvedValue({ id: 10 });
    api.deleteCashLedgerEntry.mockResolvedValue(null);
    api.previewCashBulkEntries.mockReset();
    api.previewCashBulkEntries.mockResolvedValue(bulkPreviewFixture);
    api.applyCashBulkEntries.mockReset();
    api.applyCashBulkEntries.mockResolvedValue(bulkApplyFixture);
    window.confirm = vi.fn(() => true);
  });

  it('shows per-portfolio cash-aware note in All Portfolios scope', async () => {
    renderCash({ initialSelection: { mode: 'all', id: null, name: 'All Portfolios' } });
    expect(
      await screen.findByText(/configured per portfolio/i)
    ).toBeInTheDocument();
  });

  it('shows cash-aware off status for selected legacy portfolio', async () => {
    renderCash({
      initialPortfolios: [
        {
          id: 5,
          name: 'Tester',
          base_currency: 'USD',
          is_default: true,
          is_active: true,
          cash_aware_enabled: false,
        },
      ],
      initialSelection: { mode: 'portfolio', id: 5, name: 'Tester' },
    });
    await waitFor(() => {
      expect(screen.getByText(/cash-aware mode is off/i)).toBeInTheDocument();
    });
  });

  it('calls fetchCashBalances and fetchCashLedger with all-portfolios scope', async () => {
    renderCash({ initialSelection: { mode: 'all', id: null, name: 'All Portfolios' } });
    await waitFor(() => {
      expect(api.fetchCashBalances).toHaveBeenCalledWith({
        portfolio_scope: 'all',
        display_currency: 'EUR',
      });
      expect(api.fetchCashLedger).toHaveBeenCalledWith(
        expect.objectContaining({
          portfolio_scope: 'all',
          display_currency: 'EUR',
          page: 1,
          page_size: 20,
        })
      );
    });
  });

  it('renders empty balances state', async () => {
    api.fetchCashBalances.mockResolvedValueOnce(emptyBalancesFixture);
    api.fetchCashLedger.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
    renderCash();
    expect(await screen.findByText('No cash balances')).toBeInTheDocument();
  });

  it('renders balances from backend fixture without client-side calculation', async () => {
    renderCash();
    expect((await screen.findAllByText('Scalablefolio')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('IndianMF').length).toBeGreaterThan(0);
    expect(screen.getAllByText('€12,500.00').length).toBeGreaterThan(0);
    expect(screen.getAllByText('₹50,000.00').length).toBeGreaterThan(0);
    expect(screen.getByText('Totals by currency')).toBeInTheDocument();
    expect(screen.getByText(/EUR:/)).toBeInTheDocument();
    expect(screen.getByText(/INR:/)).toBeInTheDocument();
    expect(screen.queryByText('62,500')).not.toBeInTheDocument();
  });

  it('renders paginated ledger entries with readable types', async () => {
    renderCash();
    await screen.findByText('Cash ledger');
    const tables = screen.getAllByRole('table');
    const ledger = tables[tables.length - 1];
    expect(within(ledger).getByText('Deposit')).toBeInTheDocument();
    expect(within(ledger).getByText('Withdrawal')).toBeInTheDocument();
    expect(within(ledger).getByText('€12,500.00')).toBeInTheDocument();
    expect(within(ledger).getByText('−₹1,000.00')).toBeInTheDocument();
    expect(screen.getByText('Page 1 of 1 · 2 entries')).toBeInTheDocument();
  });

  it('deposit modal shows readable backend validation error', async () => {
    api.createCashDeposit.mockRejectedValueOnce(
      new CashApiError('currency: Unsupported cash currency.', {
        status: 400,
        data: { currency: ['Unsupported cash currency.'] },
      })
    );
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /add deposit/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '100' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /record deposit/i }));

    expect(
      await within(dialog).findByText('currency: Unsupported cash currency.')
    ).toBeInTheDocument();
    expect(screen.queryByText(/body stream already read/i)).not.toBeInTheDocument();
  });

  it('deposit modal submits and refreshes data', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /add deposit/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '250' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /record deposit/i }));

    await waitFor(() => {
      expect(api.createCashDeposit).toHaveBeenCalledWith(
        expect.objectContaining({
          portfolio_id: 1,
          amount: 250,
          currency: 'EUR',
        })
      );
    });
    await waitFor(() => {
      expect(api.fetchCashBalances.mock.calls.length).toBeGreaterThan(1);
      expect(api.fetchCashLedger.mock.calls.length).toBeGreaterThan(1);
    });
    expect(screen.getByText('Deposit recorded.')).toBeInTheDocument();
  });

  it('withdrawal modal submits and refreshes data', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /add withdrawal/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '100' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /record withdrawal/i }));

    await waitFor(() => {
      expect(api.createCashWithdrawal).toHaveBeenCalledWith(
        expect.objectContaining({ portfolio_id: 1, amount: 100 })
      );
    });
    expect(screen.getByText('Withdrawal recorded.')).toBeInTheDocument();
  });

  it('shows insufficient cash shortfall details on withdrawal error', async () => {
    api.createCashWithdrawal.mockRejectedValueOnce(
      new CashApiError('Insufficient cash balance for withdrawal.', {
        required: 500,
        available: 100,
        shortfall: 400,
        currency: 'EUR',
      })
    );
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /add withdrawal/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '500' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /record withdrawal/i }));

    expect(
      await within(dialog).findByText('Insufficient cash balance for withdrawal.')
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/required/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/available/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/shortfall/i)).toBeInTheDocument();
    expect(within(dialog).getByText('€500.00')).toBeInTheDocument();
    expect(within(dialog).getByText('€100.00')).toBeInTheDocument();
    expect(within(dialog).getByText('€400.00')).toBeInTheDocument();
    expect(screen.queryByText(/body stream already read/i)).not.toBeInTheDocument();
  });

  it('all-portfolios scope requires portfolio selection in deposit modal', async () => {
    renderCash({ initialSelection: { mode: 'all', id: null, name: 'All Portfolios' } });
    await waitFor(() => expect(screen.getByText('Totals by currency')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /add deposit/i }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText(/portfolio/i)).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '100' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /record deposit/i }));
    expect(await within(dialog).findByText('Select a portfolio.')).toBeInTheDocument();
    expect(api.createCashDeposit).not.toHaveBeenCalled();
  });

  it('single portfolio scope preselects portfolio in deposit modal', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 2, name: 'IndianMF' } });
    await waitFor(() => expect(screen.getByText('IndianMF')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /add deposit/i }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText(/portfolio/i)).toHaveValue('2');

    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '50' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /record deposit/i }));

    await waitFor(() => {
      expect(api.createCashDeposit).toHaveBeenCalledWith(
        expect.objectContaining({ portfolio_id: 2 })
      );
    });
  });

  it('shows edit and delete for manual entries only', async () => {
    api.fetchCashLedger.mockResolvedValueOnce({
      items: [
        {
          id: 1,
          portfolio_id: 1,
          portfolio_name: 'Scalablefolio',
          date: '2026-06-01',
          currency: 'EUR',
          entry_type: 'CASH_DEPOSIT',
          amount: 100,
          source_of_funds: null,
          note: null,
          linked_transaction_id: null,
          transfer_group_id: null,
        },
        {
          id: 2,
          portfolio_id: 1,
          portfolio_name: 'Scalablefolio',
          date: '2026-06-02',
          currency: 'EUR',
          entry_type: 'BUY_SETTLEMENT',
          amount: -50,
          source_of_funds: null,
          note: null,
          linked_transaction_id: 99,
          transfer_group_id: null,
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    renderCash();
    await waitFor(() => {
      expect(screen.getByLabelText('Edit Deposit')).toBeInTheDocument();
      expect(screen.getByLabelText('Delete Deposit')).toBeInTheDocument();
    });
    expect(screen.queryByLabelText(/edit buy settlement/i)).not.toBeInTheDocument();
  });

  it('edit modal submits update and refreshes', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByLabelText('Edit Deposit')).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText('Edit Deposit'));
    const dialog = await screen.findByRole('dialog', { name: /edit deposit/i });
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '150' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(api.updateCashLedgerEntry).toHaveBeenCalledWith(
        10,
        expect.objectContaining({ amount: 150, currency: 'EUR' })
      );
    });
    expect(screen.getByText('Deposit updated.')).toBeInTheDocument();
  });

  it('delete confirms and refreshes ledger', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByLabelText('Delete Deposit')).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText('Delete Deposit'));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
      expect(api.deleteCashLedgerEntry).toHaveBeenCalledWith(10);
    });
    expect(screen.getByText('Cash entry deleted.')).toBeInTheDocument();
  });

  it('displays future impact error with affected entries from delete', async () => {
    api.deleteCashLedgerEntry.mockRejectedValueOnce(
      new CashApiError('This cash change would make future cash balance negative.', {
        detail: 'This cash change would make future cash balance negative.',
        currency: 'EUR',
        earliest_negative_date: '2026-06-05',
        lowest_balance: -500,
        affected_entries: [
          {
            id: 2,
            date: '2026-06-05',
            entry_type: 'BUY_SETTLEMENT',
            amount: -1000,
            linked_transaction_id: 456,
            asset_symbol: 'AAPL',
          },
        ],
      })
    );
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByLabelText('Delete Deposit')).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText('Delete Deposit'));

    await waitFor(() => {
      expect(
        screen.getByText(/future cash balance negative/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/AAPL/)).toBeInTheDocument();
      expect(screen.getByText(/add another cash deposit/i)).toBeInTheDocument();
    });
  });

  it('edit modal shows future impact when update is rejected', async () => {
    api.updateCashLedgerEntry.mockRejectedValueOnce(
      new CashApiError('This cash change would make future cash balance negative.', {
        currency: 'EUR',
        earliest_negative_date: '2026-06-04',
        lowest_balance: -200,
        affected_entries: [],
      })
    );
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByLabelText('Edit Deposit')).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText('Edit Deposit'));
    const dialog = await screen.findByRole('dialog', { name: /edit deposit/i });
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '1' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(within(dialog).getByText(/future cash balance negative/i)).toBeInTheDocument();
    });
  });

  it('uses single-portfolio scope for API reads', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => {
      expect(api.fetchCashBalances).toHaveBeenCalledWith({
        portfolio_id: 1,
        display_currency: 'EUR',
      });
    });
  });

  it('does not show Backfill Cash button', async () => {
    renderCash();
    await waitFor(() => expect(screen.getByText('Totals by currency')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /backfill cash/i })).not.toBeInTheDocument();
  });

  it('shows Add Bulk Cash Entries button', async () => {
    renderCash();
    expect(
      await screen.findByRole('button', { name: /add bulk cash entries/i })
    ).toBeInTheDocument();
  });

  it('Transfer Cash button opens modal', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    expect(await screen.findByRole('dialog', { name: /transfer cash/i })).toBeInTheDocument();
  });

  it('transfer modal single portfolio preselects source', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    const dialog = await screen.findByRole('dialog', { name: /transfer cash/i });
    expect(within(dialog).getByText('Scalablefolio')).toBeInTheDocument();
    expect(within(dialog).queryByRole('combobox', { name: /source portfolio/i })).not.toBeInTheDocument();
  });

  it('transfer modal all-portfolios requires source portfolio', async () => {
    renderCash({ initialSelection: { mode: 'all', id: null, name: 'All Portfolios' } });
    await waitFor(() => expect(screen.getByText('Totals by currency')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    const dialog = await screen.findByRole('dialog', { name: /transfer cash/i });
    expect(within(dialog).getByLabelText(/source portfolio/i)).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText(/target portfolio/i), {
      target: { value: '2' },
    });
    fireEvent.change(within(dialog).getByLabelText(/source amount/i), { target: { value: '100' } });
    fireEvent.change(within(dialog).getByLabelText(/target amount/i), { target: { value: '100' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /record transfer/i }));
    expect(await within(dialog).findByText('Select a source portfolio.')).toBeInTheDocument();
    expect(api.createCashTransfer).not.toHaveBeenCalled();
  });

  it('transfer modal target excludes source portfolio', async () => {
    renderCash({ initialSelection: { mode: 'all', id: null, name: 'All Portfolios' } });
    await waitFor(() => expect(screen.getByText('Totals by currency')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    const dialog = await screen.findByRole('dialog', { name: /transfer cash/i });
    fireEvent.change(within(dialog).getByLabelText(/source portfolio/i), {
      target: { value: '1' },
    });
    const targetOptions = within(dialog)
      .getByLabelText(/target portfolio/i)
      .querySelectorAll('option');
    const values = Array.from(targetOptions).map((o) => o.value);
    expect(values).not.toContain('1');
    expect(values).toContain('2');
  });

  it('transfer modal submit calls createCashTransfer and refreshes', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    const dialog = await screen.findByRole('dialog', { name: /transfer cash/i });
    fireEvent.change(within(dialog).getByLabelText(/target portfolio/i), {
      target: { value: '2' },
    });
    fireEvent.change(within(dialog).getByLabelText(/source amount/i), { target: { value: '250' } });
    fireEvent.change(within(dialog).getByLabelText(/target amount/i), { target: { value: '250' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /record transfer/i }));
    await waitFor(() => {
      expect(api.createCashTransfer).toHaveBeenCalledWith(
        expect.objectContaining({
          source_portfolio_id: 1,
          target_portfolio_id: 2,
          source_currency: 'EUR',
          source_amount: 250,
          target_currency: 'EUR',
          target_amount: 250,
        })
      );
    });
    await waitFor(() => {
      expect(api.fetchCashBalances.mock.calls.length).toBeGreaterThan(1);
      expect(api.fetchCashLedger.mock.calls.length).toBeGreaterThan(1);
    });
    expect(screen.getByText('Transfer recorded.')).toBeInTheDocument();
  });

  it('transfer modal shows expected field labels', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    const dialog = await screen.findByRole('dialog', { name: /transfer cash/i });
    expect(within(dialog).getByText('Source portfolio')).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/target portfolio/i)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/^date$/i)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/source currency/i)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/source amount/i)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/target currency/i)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/target amount/i)).toBeInTheDocument();
    expect(
      within(dialog).getByText(/no market fx rate is applied/i)
    ).toBeInTheDocument();
  });

  it('transfer modal submits cross-currency payload', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    const dialog = await screen.findByRole('dialog', { name: /transfer cash/i });
    fireEvent.change(within(dialog).getByLabelText(/source currency/i), {
      target: { value: 'USD' },
    });
    fireEvent.change(within(dialog).getByLabelText(/target currency/i), {
      target: { value: 'EUR' },
    });
    fireEvent.change(within(dialog).getByLabelText(/source amount/i), {
      target: { value: '1000' },
    });
    fireEvent.change(within(dialog).getByLabelText(/target amount/i), {
      target: { value: '920' },
    });
    fireEvent.change(within(dialog).getByLabelText(/target portfolio/i), {
      target: { value: '2' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /record transfer/i }));
    await waitFor(() => {
      expect(api.createCashTransfer).toHaveBeenCalledWith(
        expect.objectContaining({
          source_currency: 'USD',
          source_amount: 1000,
          target_currency: 'EUR',
          target_amount: 920,
        })
      );
    });
  });

  it('transfer modal shows insufficient cash shortfall', async () => {
    api.createCashTransfer.mockRejectedValueOnce(
      new CashApiError('Insufficient cash balance for transfer.', {
        required: 500,
        available: 100,
        shortfall: 400,
        currency: 'EUR',
      })
    );
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    const dialog = await screen.findByRole('dialog', { name: /transfer cash/i });
    fireEvent.change(within(dialog).getByLabelText(/target portfolio/i), {
      target: { value: '2' },
    });
    fireEvent.change(within(dialog).getByLabelText(/source amount/i), { target: { value: '500' } });
    fireEvent.change(within(dialog).getByLabelText(/target amount/i), { target: { value: '500' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /record transfer/i }));
    expect(
      await within(dialog).findByText('Insufficient cash balance for transfer.')
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/shortfall/i)).toBeInTheDocument();
  });

  it('transfer modal shows future impact panel', async () => {
    api.createCashTransfer.mockReset();
    api.createCashTransfer.mockRejectedValue(
      new CashApiError('This cash change would make future cash balance negative.', {
        detail: 'This cash change would make future cash balance negative.',
        currency: 'EUR',
        earliest_negative_date: '2026-06-10',
        lowest_balance: -200,
        affected_entries: [],
      })
    );
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    const dialog = await screen.findByRole('dialog', { name: /transfer cash/i });
    fireEvent.change(within(dialog).getByLabelText(/target portfolio/i), {
      target: { value: '2' },
    });
    fireEvent.change(within(dialog).getByLabelText(/source amount/i), { target: { value: '900' } });
    fireEvent.change(within(dialog).getByLabelText(/target amount/i), { target: { value: '900' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /record transfer/i }));
    await waitFor(() => {
      expect(api.createCashTransfer).toHaveBeenCalled();
    });
    expect(within(dialog).getByText(/add another cash deposit/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/2026-06-10/)).toBeInTheDocument();
  });

  it('transfer ledger rows do not show edit or delete actions', async () => {
    api.fetchCashLedger.mockResolvedValueOnce({
      items: [
        {
          id: 301,
          portfolio_id: 1,
          portfolio_name: 'Scalablefolio',
          date: '2026-06-06',
          currency: 'EUR',
          entry_type: 'TRANSFER_OUT',
          amount: -1000,
          source_of_funds: null,
          note: 'Move cash',
          linked_transaction_id: null,
          transfer_group_id: 10,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    renderCash();
    await waitFor(() => expect(screen.getByText('Transfer out')).toBeInTheDocument());
    expect(screen.queryByLabelText(/edit transfer out/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/delete transfer out/i)).not.toBeInTheDocument();
  });

  it('bulk wizard all-portfolios requires portfolio selection', async () => {
    renderCash({ initialSelection: { mode: 'all', id: null, name: 'All Portfolios' } });
    await waitFor(() => expect(screen.getByText('Totals by currency')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /add bulk cash entries/i }));
    const dialog = await screen.findByRole('dialog', { name: /add bulk cash entries/i });
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '900' } });
    fireEvent.change(within(dialog).getByLabelText(/start date/i), {
      target: { value: '2022-06-01' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /preview schedule/i }));
    expect(await within(dialog).findByText(/select a portfolio/i)).toBeInTheDocument();
    expect(api.previewCashBulkEntries).not.toHaveBeenCalled();
  });

  it('bulk wizard single portfolio preselects and previews', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /add bulk cash entries/i }));
    const dialog = await screen.findByRole('dialog', { name: /add bulk cash entries/i });
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '900' } });
    fireEvent.change(within(dialog).getByLabelText(/start date/i), {
      target: { value: '2022-06-01' },
    });
    fireEvent.change(within(dialog).getByLabelText(/end date/i), {
      target: { value: '2022-12-01' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /preview schedule/i }));
    await waitFor(() => {
      expect(api.previewCashBulkEntries).toHaveBeenCalledWith(
        expect.objectContaining({
          portfolio_id: 1,
          entry_type: 'CASH_DEPOSIT',
          currency: 'EUR',
          amount: 900,
          start_date: '2022-06-01',
          end_date: '2022-12-01',
          frequency: 'monthly',
        })
      );
    });
    expect(await within(dialog).findByText('Scheduled entries')).toBeInTheDocument();
    expect(within(dialog).getAllByText('€900.00').length).toBeGreaterThan(0);
    expect(within(dialog).getByText('2022-06-01')).toBeInTheDocument();
  });

  it('bulk apply sends confirmed via applyCashBulkEntries and refreshes', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    const balanceCallsBefore = api.fetchCashBalances.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: /add bulk cash entries/i }));
    let dialog = await screen.findByRole('dialog', { name: /add bulk cash entries/i });
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '900' } });
    fireEvent.change(within(dialog).getByLabelText(/start date/i), {
      target: { value: '2022-06-01' },
    });
    fireEvent.change(within(dialog).getByLabelText(/end date/i), {
      target: { value: '2022-12-01' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /preview schedule/i }));
    await within(dialog).findByRole('button', { name: /apply bulk entries/i });
    fireEvent.click(within(dialog).getByRole('button', { name: /apply bulk entries/i }));

    await waitFor(() => {
      expect(api.applyCashBulkEntries).toHaveBeenCalledWith(
        expect.objectContaining({ portfolio_id: 1, frequency: 'monthly' })
      );
      expect(api.fetchCashBalances.mock.calls.length).toBeGreaterThan(balanceCallsBefore);
    });
    dialog = await screen.findByRole('dialog', { name: /add bulk cash entries/i });
    expect(within(dialog).getByText('Created')).toBeInTheDocument();
  });

  it('bulk wizard displays preview validation error', async () => {
    api.previewCashBulkEntries.mockRejectedValueOnce(
      new CashApiError('start_date must be on or before end_date', { status: 400 })
    );
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /add bulk cash entries/i }));
    const dialog = await screen.findByRole('dialog', { name: /add bulk cash entries/i });
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '900' } });
    fireEvent.change(within(dialog).getByLabelText(/start date/i), {
      target: { value: '2022-12-01' },
    });
    fireEvent.change(within(dialog).getByLabelText(/end date/i), {
      target: { value: '2022-06-01' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /preview schedule/i }));
    expect(
      await within(dialog).findByText(/start date must be on or before end date/i)
    ).toBeInTheDocument();
  });

  it('bulk apply prevents double submit', async () => {
    let resolveApply;
    api.applyCashBulkEntries.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveApply = () => resolve(bulkApplyFixture);
        })
    );
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByText('Scalablefolio')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /add bulk cash entries/i }));
    const dialog = await screen.findByRole('dialog', { name: /add bulk cash entries/i });
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '900' } });
    fireEvent.change(within(dialog).getByLabelText(/start date/i), {
      target: { value: '2022-06-01' },
    });
    fireEvent.change(within(dialog).getByLabelText(/end date/i), {
      target: { value: '2022-12-01' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /preview schedule/i }));
    const applyBtn = await within(dialog).findByRole('button', {
      name: /apply bulk entries/i,
    });
    fireEvent.click(applyBtn);
    fireEvent.click(applyBtn);
    expect(api.applyCashBulkEntries).toHaveBeenCalledTimes(1);
    resolveApply();
    await waitFor(() => expect(within(dialog).getByText('Created')).toBeInTheDocument());
  });
});

describe('Cash routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchPortfolios.mockResolvedValue(activePortfolios);
    api.getSettings.mockResolvedValue({ display_currency: 'EUR', tax_rate_percentage: 26.375 });
    api.fetchCashBalances.mockResolvedValue(emptyBalancesFixture);
    api.fetchCashLedger.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
  });

  it('/cash route renders Cash page', async () => {
    render(
      <MemoryRouter initialEntries={['/cash']}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByRole('heading', { name: /^cash$/i })).toBeInTheDocument();
    expect(
      screen.getByText(/native cash balances by portfolio and currency/i)
    ).toBeInTheDocument();
  });
});
