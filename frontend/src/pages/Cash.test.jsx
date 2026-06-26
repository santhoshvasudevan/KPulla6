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
    fetchCashOverview: vi.fn(),
    fetchCashBalances: vi.fn(),
    fetchCashLedger: vi.fn(),
    createCashDeposit: vi.fn(),
    createCashWithdrawal: vi.fn(),
    createCashTransfer: vi.fn(),
    updateCashLedgerEntry: vi.fn(),
    deleteCashLedgerEntry: vi.fn(),
    reverseCashLedgerEntry: vi.fn(),
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

const overviewFixture = {
  portfolio_scope: 'all',
  as_of_date: '2026-06-04',
  display_currency: 'EUR',
  rows: [
    {
      ledger_type: 'BROKER_CASH',
      portfolio_id: 1,
      portfolio_name: 'Scalablefolio',
      currency: 'EUR',
      balance: 12500,
      account_label: 'Broker Cash',
      available_for: 'securities / broker transactions',
      source: 'cash_ledger_entries',
      balance_display: 12500,
      display_currency: 'EUR',
    },
    {
      ledger_type: 'BROKER_CASH',
      portfolio_id: 2,
      portfolio_name: 'IndianMF',
      currency: 'INR',
      balance: 50000,
      account_label: 'Broker Cash',
      available_for: 'securities / broker transactions',
      source: 'cash_ledger_entries',
      balance_display: 550,
      display_currency: 'EUR',
    },
    {
      ledger_type: 'BANK_CASH',
      bank_account_id: 1,
      bank_account_name: 'Savings',
      institution_name: 'HDFC',
      account_number: 'ACC-1',
      portfolio_id: 1,
      portfolio_name: 'Scalablefolio',
      portfolio_assignment_status: 'ASSIGNED',
      currency: 'INR',
      balance: 100000,
      include_in_portfolio_value: true,
      account_label: 'Bank Cash',
      available_for: 'fixed deposits / bank products',
      source: 'cash_movements',
      balance_display: 1100,
      display_currency: 'EUR',
    },
  ],
  totals: {
    as_of_date: '2026-06-04',
    display_currency: 'EUR',
    fx_status: 'ok',
    broker_cash_display: 13050,
    bank_cash_display: 1100,
    total_cash_display: 14150,
    by_currency: [
      { currency: 'EUR', broker_cash: 12500, bank_cash: 0, total_cash: 12500 },
      { currency: 'INR', broker_cash: 50000, bank_cash: 100000, total_cash: 150000 },
    ],
  },
  warnings: [],
  excluded_unassigned_bank_account_count: 1,
  excluded_ambiguous_bank_account_count: 0,
};

const emptyOverviewFixture = {
  portfolio_scope: 'all',
  as_of_date: '2026-06-04',
  display_currency: 'EUR',
  rows: [],
  totals: {
    as_of_date: '2026-06-04',
    display_currency: 'EUR',
    fx_status: 'ok',
    broker_cash_display: 0,
    bank_cash_display: 0,
    total_cash_display: 0,
    by_currency: [],
  },
  warnings: [],
  excluded_unassigned_bank_account_count: 0,
  excluded_ambiguous_bank_account_count: 0,
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
      details: 'Bank · Seed',
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
      details: 'Cash withdrawal',
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
    <MemoryRouter>
      <PortfolioProvider
        disableFetch
        initialPortfolios={initialPortfolios}
        initialSelection={initialSelection}
        initialDisplayCurrency="EUR"
      >
        <Cash />
      </PortfolioProvider>
    </MemoryRouter>
  );
}

async function waitForCashPageReady() {
  await screen.findByText('Broker Cash');
}

describe('Cash page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchCashOverview.mockResolvedValue(overviewFixture);
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
    api.reverseCashLedgerEntry.mockResolvedValue({
      original: { id: 10, is_reversed: true },
      reversal: { id: 301, entry_type: 'CASH_WITHDRAWAL', amount: -100 },
      message: 'Broker cash entry reversed.',
    });
    api.previewCashBulkEntries.mockReset();
    api.previewCashBulkEntries.mockResolvedValue(bulkPreviewFixture);
    api.applyCashBulkEntries.mockReset();
    api.applyCashBulkEntries.mockResolvedValue(bulkApplyFixture);
    window.confirm = vi.fn(() => true);
  });

  it('shows page header with unified cash title and subtitle', async () => {
    renderCash();
    expect(
      await screen.findByRole('heading', { name: /cash \/ liquid holdings/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/broker cash and bank cash are shown separately/i)
    ).toBeInTheDocument();
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

  it('calls fetchCashOverview and fetchCashLedger with all-portfolios scope', async () => {
    renderCash({ initialSelection: { mode: 'all', id: null, name: 'All Portfolios' } });
    await waitFor(() => {
      expect(api.fetchCashOverview).toHaveBeenCalledWith({
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

  it('renders empty cash holdings state', async () => {
    api.fetchCashOverview.mockResolvedValueOnce(emptyOverviewFixture);
    api.fetchCashLedger.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
    renderCash();
    expect(await screen.findByText('No cash holdings')).toBeInTheDocument();
    expect(screen.getByText('No broker cash')).toBeInTheDocument();
    expect(screen.getByText('No bank cash')).toBeInTheDocument();
  });

  it('shows Total Cash, Broker Cash, and Bank Cash KPI cards', async () => {
    renderCash();
    expect(await screen.findByLabelText('Cash holdings overview')).toBeInTheDocument();
    expect(screen.getByText('Total Cash (EUR)')).toBeInTheDocument();
    expect(screen.getByText('Broker Cash (EUR)')).toBeInTheDocument();
    expect(screen.getByText('Bank Cash (EUR)')).toBeInTheDocument();
    expect(screen.getByText('€14,150.00')).toBeInTheDocument();
  });

  it('renders broker and bank cash rows from overview API', async () => {
    renderCash();
    expect(await screen.findByRole('heading', { name: /cash \/ liquid holdings/i })).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { name: 'Broker Cash' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('heading', { name: 'Bank Cash' }).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Scalablefolio').length).toBeGreaterThan(0);
    expect(screen.getAllByText('IndianMF').length).toBeGreaterThan(0);
    expect(screen.getAllByText('€12,500.00').length).toBeGreaterThan(0);
    expect(screen.getByText('HDFC')).toBeInTheDocument();
    expect(screen.getByText('Savings')).toBeInTheDocument();
    expect(screen.getAllByText('securities / broker transactions').length).toBeGreaterThan(0);
    expect(screen.getByText('fixed deposits / bank products')).toBeInTheDocument();
    expect(screen.queryByText('62,500')).not.toBeInTheDocument();
  });

  it('shows Broker Cash actions label and all broker action buttons', async () => {
    renderCash();
    expect(await screen.findByText('Broker Cash actions')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /add deposit/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /add withdrawal/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /add bulk cash entries/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /transfer cash/i })).toBeInTheDocument();
  });

  it('renders source diagnostics for broker and bank rows', async () => {
    const { container } = renderCash();
    await screen.findByRole('heading', { name: 'Broker Cash' });
    const brokerSection = container.querySelector('.cash-page__broker-cash');
    const bankSection = container.querySelector('.cash-page__bank-cash');
    expect(
      within(brokerSection).getAllByText('Broker cash ledger (CashLedgerEntry)').length
    ).toBeGreaterThan(0);
    expect(
      within(bankSection).getByText('Bank account ledger (CashMovement)')
    ).toBeInTheDocument();
  });

  it('keeps BROKER_CASH rows in broker section and BANK_CASH rows in bank section', async () => {
    const { container } = renderCash();
    await screen.findByText('Broker Cash');
    const brokerSection = container.querySelector('.cash-page__broker-cash');
    const bankSection = container.querySelector('.cash-page__bank-cash');
    expect(brokerSection).toBeTruthy();
    expect(bankSection).toBeTruthy();
    expect(within(brokerSection).getByText('IndianMF')).toBeInTheDocument();
    expect(within(brokerSection).queryByText('HDFC')).not.toBeInTheDocument();
    expect(within(bankSection).getByText('HDFC')).toBeInTheDocument();
    expect(within(bankSection).queryByText('IndianMF')).not.toBeInTheDocument();
  });

  it('uses broker and bank KPI totals from overview without swapping', async () => {
    renderCash();
    const overview = await screen.findByLabelText('Cash holdings overview');
    expect(within(overview).getByText('Broker Cash (EUR)')).toBeInTheDocument();
    expect(within(overview).getByText('Bank Cash (EUR)')).toBeInTheDocument();
    expect(within(overview).getByText('€13,050.00')).toBeInTheDocument();
    expect(within(overview).getByText('€1,100.00')).toBeInTheDocument();
    expect(within(overview).queryByText('€110,000.00')).not.toBeInTheDocument();
  });

  it('renders IndianInvestments-like fixture with broker 0 INR and bank 1,109,389 INR', async () => {
    const indianInvestmentsOverview = {
      portfolio_scope: 'single',
      portfolio_id: 42,
      as_of_date: '2026-06-04',
      rows: [
        {
          ledger_type: 'BROKER_CASH',
          portfolio_id: 42,
          portfolio_name: 'IndianInvestments',
          currency: 'INR',
          balance: 0,
          account_label: 'Broker Cash',
          available_for: 'securities / broker transactions',
          source: 'cash_ledger_entries',
        },
        {
          ledger_type: 'BANK_CASH',
          bank_account_id: 7,
          bank_account_name: 'Savings',
          institution_name: 'HDFC',
          account_number: 'XXXX1234',
          portfolio_id: 42,
          portfolio_name: 'IndianInvestments',
          portfolio_assignment_status: 'ASSIGNED',
          currency: 'INR',
          balance: 1109389,
          include_in_portfolio_value: true,
          account_label: 'Bank Cash',
          available_for: 'fixed deposits / bank products',
          source: 'cash_movements',
        },
      ],
      totals: {
        as_of_date: '2026-06-04',
        by_currency: [
          { currency: 'INR', broker_cash: 0, bank_cash: 1109389, total_cash: 1109389 },
        ],
        broker_cash: 0,
        bank_cash: 1109389,
        total_cash: 1109389,
      },
      warnings: [],
      excluded_unassigned_bank_account_count: 0,
      excluded_ambiguous_bank_account_count: 0,
    };
    api.fetchCashOverview.mockResolvedValue(indianInvestmentsOverview);
    renderCash({
      initialSelection: { mode: 'portfolio', id: 42, name: 'IndianInvestments' },
      initialPortfolios: [
        { id: 42, name: 'IndianInvestments', is_active: true, base_currency: 'INR' },
      ],
    });
    const brokerSection = await waitFor(() => {
      const section = document.querySelector('.cash-page__broker-cash');
      if (!section) throw new Error('broker section not ready');
      return section;
    });
    const bankSection = document.querySelector('.cash-page__bank-cash');
    expect(within(brokerSection).getByText('₹0.00')).toBeInTheDocument();
    expect(within(bankSection).getByText('₹1,109,389.00')).toBeInTheDocument();
    const overview = screen.getByLabelText('Cash holdings overview');
    expect(within(overview).getByText('Total Cash (INR)')).toBeInTheDocument();
    expect(within(overview).getByText('Broker Cash (INR)')).toBeInTheDocument();
    expect(within(overview).getByText('Bank Cash (INR)')).toBeInTheDocument();
    expect(within(overview).getAllByText('₹1,109,389.00').length).toBeGreaterThanOrEqual(1);
    expect(within(overview).getByText('₹0.00')).toBeInTheDocument();
  });

  it('does not render bank cash mutation forms on Cash page', async () => {
    renderCash();
    await screen.findByText('Bank Cash');
    expect(screen.queryByRole('button', { name: /add bank/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/bank movement/i)).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /manage bank accounts/i })).toBeInTheDocument();
  });

  it('always shows unassigned toggle even when no exclusions', async () => {
    api.fetchCashOverview.mockResolvedValueOnce({
      ...overviewFixture,
      excluded_unassigned_bank_account_count: 0,
      excluded_ambiguous_bank_account_count: 0,
      warnings: [],
    });
    renderCash();
    expect(
      await screen.findByLabelText(/show unassigned \/ ambiguous bank accounts/i)
    ).toBeInTheDocument();
  });

  it('shows bank assignment status and include-in-portfolio-value indicator', async () => {
    renderCash();
    expect(await screen.findByText('Assigned')).toBeInTheDocument();
    expect(screen.getByText('Include in portfolio value')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
  });

  it('shows excluded unassigned bank account warning and toggle', async () => {
    renderCash();
    expect(
      await screen.findByText(/1 bank account\(s\) excluded from this view/i)
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(/show unassigned \/ ambiguous bank accounts/i)
    ).toBeInTheDocument();
  });

  it('passes include_unassigned when toggle is enabled', async () => {
    renderCash();
    await screen.findByLabelText(/show unassigned \/ ambiguous bank accounts/i);
    fireEvent.click(screen.getByLabelText(/show unassigned \/ ambiguous bank accounts/i));
    await waitFor(() => {
      expect(api.fetchCashOverview).toHaveBeenCalledWith(
        expect.objectContaining({ include_unassigned: true })
      );
    });
  });

  it('shows FX warning when overview reports partial FX', async () => {
    api.fetchCashOverview.mockResolvedValueOnce({
      ...overviewFixture,
      totals: { ...overviewFixture.totals, fx_status: 'partial', total_cash_display: null },
      warnings: ['Display-currency total may be incomplete due to missing FX rates.'],
    });
    renderCash();
    expect(
      await screen.findByText(/display-currency totals may be incomplete/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/display-currency total may be incomplete due to missing fx rates/i)
    ).toBeInTheDocument();
  });

  it('shows overview API error state', async () => {
    api.fetchCashOverview.mockRejectedValueOnce(new Error('Overview unavailable'));
    renderCash();
    expect(await screen.findByText('Could not load cash overview')).toBeInTheDocument();
    expect(screen.getByText('Overview unavailable')).toBeInTheDocument();
  });

  it('links to Settings bank accounts from bank cash section', async () => {
    renderCash();
    const link = await screen.findByRole('link', { name: /manage bank accounts/i });
    expect(link).toHaveAttribute('href', '/settings#settings-bank-accounts');
  });

  it('renders paginated ledger entries with readable types', async () => {
    renderCash();
    await screen.findByText('Broker Cash ledger');
    const tables = screen.getAllByRole('table');
    const ledger = tables[tables.length - 1];
    expect(within(ledger).getByText('Deposit')).toBeInTheDocument();
    expect(within(ledger).getByText('Withdrawal')).toBeInTheDocument();
    expect(within(ledger).getByText('€12,500.00')).toBeInTheDocument();
    expect(within(ledger).getByText('−₹1,000.00')).toBeInTheDocument();
    expect(within(ledger).getByText('Bank · Seed')).toBeInTheDocument();
    expect(screen.getByText('Page 1 of 1 · 2 entries')).toBeInTheDocument();
  });

  it('uses premium sections for broker cash, bank cash, and ledger', async () => {
    const { container } = renderCash();
    await screen.findByText('Broker Cash');
    expect(container.querySelectorAll('.cash-page__section').length).toBeGreaterThanOrEqual(3);
    expect(container.querySelector('.cash-page__broker-cash.ui-data-table-shell')).toBeTruthy();
    expect(container.querySelector('.cash-page__bank-cash.ui-data-table-shell')).toBeTruthy();
    expect(container.querySelector('.cash-page__ledger.ui-app-card')).toBeTruthy();
  });

  it('renders TAX_WITHHELD row with protected actions', async () => {
    api.fetchCashLedger.mockResolvedValueOnce({
      items: [
        {
          id: 21,
          portfolio_id: 1,
          portfolio_name: 'Scalablefolio',
          date: '2026-06-02',
          currency: 'EUR',
          entry_type: 'TAX_WITHHELD',
          amount: -68,
          details:
            'Tax withheld / broker adjustment for SELL AAPL · Calculated 998 EUR · Actual received 930 EUR · Withheld 68 EUR',
          linked_transaction_id: 42,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    renderCash();
    await screen.findByText('Broker Cash ledger');
    const details =
      'Tax withheld / broker adjustment for SELL AAPL · Calculated 998 EUR · Actual received 930 EUR · Withheld 68 EUR';
    expect(screen.getByText(details)).toBeInTheDocument();
    expect(screen.getAllByText('Tax withheld').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
  });

  it('renders backend-provided ledger details column', async () => {
    api.fetchCashLedger.mockResolvedValueOnce({
      items: [
        {
          id: 20,
          portfolio_id: 1,
          portfolio_name: 'Scalablefolio',
          date: '2026-06-02',
          currency: 'EUR',
          entry_type: 'BUY_SETTLEMENT',
          amount: -1005,
          details: 'Buy AAPL · Qty 10 · Price 100 EUR · Fees 5 EUR',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    renderCash();
    await screen.findByText('Broker Cash ledger');
    expect(
      screen.getByText('Buy AAPL · Qty 10 · Price 100 EUR · Fees 5 EUR')
    ).toBeInTheDocument();
    expect(screen.getAllByRole('columnheader', { name: /^source$/i }).length).toBeGreaterThan(0);
  });

  it('deposit modal shows readable backend validation error', async () => {
    api.createCashDeposit.mockRejectedValueOnce(
      new CashApiError('currency: Unsupported cash currency.', {
        status: 400,
        data: { currency: ['Unsupported cash currency.'] },
      })
    );
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitForCashPageReady();

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
    await waitForCashPageReady();

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
      expect(api.fetchCashOverview.mock.calls.length).toBeGreaterThan(1);
      expect(api.fetchCashLedger.mock.calls.length).toBeGreaterThan(1);
    });
    expect(screen.getByText('Deposit recorded.')).toBeInTheDocument();
  });

  it('withdrawal modal submits and refreshes data', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitForCashPageReady();

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
    await waitForCashPageReady();

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
    await waitFor(() => expect(screen.getByText('Broker Cash')).toBeInTheDocument());

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

  it('shows reverse action for reversible manual deposit and refreshes overview', async () => {
    api.fetchCashLedger.mockResolvedValueOnce({
      items: [
        {
          id: 10,
          portfolio_id: 1,
          portfolio_name: 'Scalablefolio',
          date: '2023-09-24',
          currency: 'INR',
          entry_type: 'CASH_DEPOSIT',
          amount: 1109389,
          source_of_funds: 'salary',
          note: null,
          linked_transaction_id: null,
          transfer_group_id: null,
          is_reversal: false,
          is_reversed: false,
          is_reversible: true,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitFor(() => expect(screen.getByLabelText('Reverse Deposit')).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText('Reverse Deposit'));
    const dialog = await screen.findByRole('dialog', { name: /reverse broker cash entry/i });
    expect(
      within(dialog).getByText(/does not affect bank cash/i)
    ).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText(/reason/i), {
      target: { value: 'Recorded in broker ledger by mistake' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /reverse entry/i }));

    await waitFor(() => {
      expect(api.reverseCashLedgerEntry).toHaveBeenCalledWith(
        10,
        expect.objectContaining({ reason: 'Recorded in broker ledger by mistake' })
      );
      expect(api.fetchCashOverview.mock.calls.length).toBeGreaterThan(1);
    });
    expect(screen.getByText('Broker cash entry reversed.')).toBeInTheDocument();
  });

  it('hides reverse action for protected ledger rows', async () => {
    api.fetchCashLedger.mockResolvedValueOnce({
      items: [
        {
          id: 20,
          portfolio_id: 1,
          portfolio_name: 'Scalablefolio',
          date: '2026-06-02',
          currency: 'EUR',
          entry_type: 'BUY_SETTLEMENT',
          amount: -1005,
          linked_transaction_id: 42,
          transfer_group_id: null,
          is_reversible: false,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    renderCash();
    await screen.findByText('Broker Cash ledger');
    expect(screen.queryByLabelText(/reverse/i)).not.toBeInTheDocument();
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
      expect(api.fetchCashOverview).toHaveBeenCalledWith({
        portfolio_id: 1,
        display_currency: 'EUR',
      });
    });
  });

  it('does not show Backfill Cash button', async () => {
    renderCash();
    await waitFor(() => expect(screen.getByText('Broker Cash')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /backfill cash/i })).not.toBeInTheDocument();
  });

  it('shows Add Bulk Cash Entries button', async () => {
    renderCash();
    expect(
      await screen.findByRole('button', { name: /add bulk cash entries/i })
    ).toBeInTheDocument();
  });

  it('bulk wizard opens modal when button clicked', async () => {
    renderCash();
    await waitFor(() => expect(screen.getByText('Broker Cash')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /add bulk cash entries/i }));
    expect(
      await screen.findByRole('dialog', { name: /add bulk cash entries/i })
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole('dialog', { name: /add bulk cash entries/i })).getByText(
        /amounts and dates come from the server preview/i
      )
    ).toBeInTheDocument();
  });

  it('Transfer Cash button opens modal', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitForCashPageReady();
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    expect(await screen.findByRole('dialog', { name: /transfer cash/i })).toBeInTheDocument();
  });

  it('transfer modal single portfolio preselects source', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitForCashPageReady();
    fireEvent.click(screen.getByRole('button', { name: /transfer cash/i }));
    const dialog = await screen.findByRole('dialog', { name: /transfer cash/i });
    expect(within(dialog).getByText('Scalablefolio')).toBeInTheDocument();
    expect(within(dialog).queryByRole('combobox', { name: /source portfolio/i })).not.toBeInTheDocument();
  });

  it('transfer modal all-portfolios requires source portfolio', async () => {
    renderCash({ initialSelection: { mode: 'all', id: null, name: 'All Portfolios' } });
    await waitFor(() => expect(screen.getByText('Broker Cash')).toBeInTheDocument());
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
    await waitFor(() => expect(screen.getByText('Broker Cash')).toBeInTheDocument());
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
    await waitForCashPageReady();
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
      expect(api.fetchCashOverview.mock.calls.length).toBeGreaterThan(1);
      expect(api.fetchCashLedger.mock.calls.length).toBeGreaterThan(1);
    });
    expect(screen.getByText('Transfer recorded.')).toBeInTheDocument();
  });

  it('transfer modal shows expected field labels', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitForCashPageReady();
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
    await waitForCashPageReady();
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
    await waitForCashPageReady();
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
    await waitForCashPageReady();
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
    await waitFor(() => expect(screen.getByText('Broker Cash')).toBeInTheDocument());
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
    await waitForCashPageReady();
    fireEvent.click(screen.getByRole('button', { name: /add bulk cash entries/i }));
    const dialog = await screen.findByRole('dialog', { name: /add bulk cash entries/i });
    fireEvent.change(within(dialog).getByLabelText(/amount/i), { target: { value: '900' } });
    fireEvent.change(within(dialog).getByLabelText(/start date/i), {
      target: { value: '2022-06-01' },
    });
    fireEvent.change(within(dialog).getByLabelText(/end date/i), {
      target: { value: '2022-12-01' },
    });
    fireEvent.change(within(dialog).getByLabelText(/source of funds/i), {
      target: { value: 'Monthly contribution' },
    });
    fireEvent.change(within(dialog).getByLabelText(/^note$/i), {
      target: { value: 'Historical contribution' },
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
          source_of_funds: 'Monthly contribution',
          note: 'Historical contribution',
        })
      );
    });
    expect(await within(dialog).findByText('Scheduled entries')).toBeInTheDocument();
    expect(within(dialog).getByText('Total by currency')).toBeInTheDocument();
    expect(within(dialog).getByText('€6,300.00')).toBeInTheDocument();
    expect(within(dialog).getAllByText('€900.00').length).toBeGreaterThan(0);
    expect(within(dialog).getByText('2022-06-01')).toBeInTheDocument();
  });

  it('bulk apply sends confirmed via applyCashBulkEntries and refreshes', async () => {
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitForCashPageReady();
    const overviewCallsBefore = api.fetchCashOverview.mock.calls.length;
    const ledgerCallsBefore = api.fetchCashLedger.mock.calls.length;

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
      expect(api.fetchCashOverview.mock.calls.length).toBeGreaterThan(overviewCallsBefore);
      expect(api.fetchCashLedger.mock.calls.length).toBeGreaterThan(ledgerCallsBefore);
    });
    dialog = await screen.findByRole('dialog', { name: /add bulk cash entries/i });
    expect(within(dialog).getByText('Created')).toBeInTheDocument();
  });

  it('bulk wizard displays preview validation error', async () => {
    api.previewCashBulkEntries.mockRejectedValueOnce(
      new CashApiError('start_date must be on or before end_date', { status: 400 })
    );
    renderCash({ initialSelection: { mode: 'portfolio', id: 1, name: 'Scalablefolio' } });
    await waitForCashPageReady();
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
    await waitForCashPageReady();
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
    api.fetchCashOverview.mockResolvedValue(emptyOverviewFixture);
    api.fetchCashLedger.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
  });

  it('/cash route renders Cash page', async () => {
    render(
      <MemoryRouter initialEntries={['/cash']}>
        <App />
      </MemoryRouter>
    );
    expect(
      await screen.findByRole('heading', { name: /cash \/ liquid holdings/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/broker cash and bank cash are shown separately/i)
    ).toBeInTheDocument();
  });
});
