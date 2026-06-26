import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import FixedDeposits from './FixedDeposits';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', () => ({
  fetchFixedDeposits: vi.fn(),
  fetchPortfolios: vi.fn(),
  fetchBankAccounts: vi.fn(),
  fetchBankAccountBalance: vi.fn(),
  createFixedDeposit: vi.fn(),
  updateFixedDeposit: vi.fn(),
  deleteFixedDeposit: vi.fn(),
  cancelFixedDeposit: vi.fn(),
  fetchFixedDepositInterestPayments: vi.fn(),
  createFixedDepositInterestPayment: vi.fn(),
  reverseFixedDepositInterestPayment: vi.fn(),
  markFixedDepositMatured: vi.fn(),
  renewFixedDeposit: vi.fn(),
  settleFixedDeposit: vi.fn(),
  fetchFixedDepositInterestReport: vi.fn(),
  exportFixedDepositInterestReportCsv: vi.fn(),
  downloadBlobFile: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
  FixedDepositApiError: class FixedDepositApiError extends Error {
    constructor(message, extras = {}) {
      super(message);
      this.name = 'FixedDepositApiError';
      Object.assign(this, extras);
    }
  },
}));

const sampleFd = {
  id: 1,
  portfolio_id: 1,
  portfolio_name: 'Default Portfolio',
  bank_account_id: 10,
  bank_account_name: 'Savings',
  institution_name: 'HDFC',
  deposit_account_number: 'FD-001',
  principal_amount: 100000,
  currency: 'INR',
  interest_rate_percent: 7,
  interest_payout_frequency: 'QUARTERLY',
  investment_date: '2024-01-01',
  maturity_date: '2026-01-01',
  nominee_name: null,
  status: 'ACTIVE',
  is_active: true,
  has_opening_cash_movement: true,
  opening_cash_movement_id: 99,
};

const seededBankAccount = {
  id: 10,
  name: 'Savings',
  institution_name: 'HDFC',
  currency: 'INR',
  opening_balance: 250000,
  current_balance: 250000,
  portfolio_id: 1,
  portfolio_name: 'Default Portfolio',
  portfolio_assignment_status: 'ASSIGNED',
  has_ledger_entries: true,
  opening_balance_seeded: true,
  balance_source: 'ledger',
  is_active: true,
};

const unassignedBankAccount = {
  id: 12,
  name: 'Unassigned',
  institution_name: 'ICICI',
  currency: 'INR',
  opening_balance: 100000,
  current_balance: 100000,
  portfolio_id: null,
  portfolio_name: null,
  portfolio_assignment_status: 'UNASSIGNED',
  has_ledger_entries: true,
  opening_balance_seeded: true,
  balance_source: 'ledger',
  is_active: true,
};

const unseededBankAccount = {
  id: 11,
  name: 'NRE',
  institution_name: 'SBI',
  currency: 'INR',
  opening_balance: 250000,
  current_balance: 250000,
  has_ledger_entries: false,
  opening_balance_seeded: false,
  balance_source: 'manual',
  is_active: true,
};

function renderPage() {
  return render(
    <PortfolioProvider disableFetch initialPortfolios={[{ id: 1, name: 'Default Portfolio', is_active: true }]}>
      <FixedDeposits />
    </PortfolioProvider>
  );
}

describe('FixedDeposits page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
    api.fetchFixedDeposits.mockResolvedValue([sampleFd]);
    api.fetchPortfolios.mockResolvedValue([{ id: 1, name: 'Default Portfolio', is_active: true }]);
    api.fetchBankAccounts.mockResolvedValue([seededBankAccount]);
    api.fetchBankAccountBalance.mockResolvedValue({
      bank_account_id: 10,
      currency: 'INR',
      current_balance: 250000,
      balance_as_of_date: 250000,
      as_of_date: '2026-06-24',
      opening_balance_seeded: true,
      has_ledger_entries: true,
    });
    api.fetchFixedDepositInterestPayments.mockResolvedValue([]);
    api.fetchFixedDepositInterestReport.mockResolvedValue({
      rows: [],
      totals: {
        gross_interest: 0,
        tax_withheld: 0,
        net_interest: 0,
        currency: 'INR',
        row_count: 0,
        fx_status: 'ok',
      },
      warnings: [],
    });
  });

  it('renders page header and primary action', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /fixed deposits/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /add fixed deposit/i })).toBeInTheDocument();
    });
  });

  it('renders overview KPI cards and section navigation', async () => {
    renderPage();
    await waitFor(() => {
      const overview = screen.getByLabelText(/fixed deposit overview/i);
      expect(within(overview).getByText('Total deposits')).toBeInTheDocument();
      expect(within(overview).getByText('Active')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /overview/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /deposits/i })).toBeInTheDocument();
    });
  });

  it('renders fixed deposit list from API', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('HDFC')).toBeInTheDocument();
      expect(screen.getByText('FD-001')).toBeInTheDocument();
      expect(screen.getByText('Quarterly')).toBeInTheDocument();
      expect(screen.getByRole('status', { name: 'Active' })).toBeInTheDocument();
    });
  });

  it('shows bank account warning when none exist', async () => {
    api.fetchBankAccounts.mockResolvedValue([]);
    api.fetchFixedDeposits.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/add at least one active bank account/i)).toBeInTheDocument();
    });
  });

  it('create modal shows current and as-of ledger balance labels', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    expect(
      screen.getByText(/creating a fixed deposit will debit the principal from the linked bank account/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/current ledger balance:/i)).toBeInTheDocument();
    expect(
      screen.getByText(/fd creation validates the selected bank account ledger balance as of the investment date/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/portfolio cash \(cash tab\) and bank ledger/i)).toBeInTheDocument();
  });

  it('shows backdated ledger note when investment date is set', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });

    expect(
      screen.getByText(/opening balance or cash deposit is recorded on or before the fd investment date/i)
    ).toBeInTheDocument();
  });

  it('shows derived portfolio when assigned bank account is selected', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));

    expect(screen.getByDisplayValue('Default Portfolio')).toBeInTheDocument();
    expect(
      screen.getByText(
        /fd portfolio is derived from the selected bank account's linked portfolio \(default portfolio\)/i
      )
    ).toBeInTheDocument();
  });

  it('blocks create when bank account portfolio is unassigned', async () => {
    api.fetchBankAccounts.mockResolvedValueOnce([unassignedBankAccount]);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));

    expect(
      screen.getByText(
        /link this bank account to a portfolio in settings → bank accounts before creating an fd/i
      )
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^create$/i })).toBeDisabled();
  });

  it('shows structured backend portfolio conflict details', async () => {
    const err = new api.FixedDepositApiError(
      'Fixed deposit portfolio must match the bank account portfolio (Default Portfolio).',
      {
        detail: 'Fixed deposit portfolio must match the bank account portfolio (Default Portfolio).',
        bank_account_id: 10,
        bank_account_portfolio_id: 1,
        bank_account_portfolio_name: 'Default Portfolio',
        requested_portfolio_id: 2,
        portfolio_assignment_status: 'ASSIGNED',
        hint: 'Select a bank account linked to the intended portfolio, or assign the bank account first.',
      }
    );
    api.createFixedDeposit.mockRejectedValueOnce(err);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/institution/i), { target: { value: 'HDFC' } });
    fireEvent.change(screen.getByLabelText(/deposit account number/i), {
      target: { value: 'FD-NEW' },
    });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    fireEvent.change(screen.getByLabelText(/interest rate/i), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/maturity date/i), { target: { value: '2026-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: /^create$/i }));

    await waitFor(() => {
      const panel = document.querySelector('.fd-form__error-panel');
      expect(panel).toBeTruthy();
      expect(panel).toHaveTextContent(/bank account portfolio: default portfolio/i);
      expect(panel).toHaveTextContent(/portfolio assignment: assigned/i);
    });
  });

  it('shows structured backend insufficient balance details and focuses error', async () => {
    const err = new api.FixedDepositApiError('Insufficient bank account balance for this movement.', {
      detail: 'Insufficient bank account balance for this movement.',
      required: 100000,
      available: 0,
      available_as_of_date: 0,
      current_balance: 1359389,
      shortfall: 100000,
      currency: 'INR',
      investment_date: '2024-01-01',
      hint: 'For backdated FDs, record or seed bank cash on or before the investment date.',
    });
    api.createFixedDeposit.mockRejectedValueOnce(err);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/institution/i), { target: { value: 'HDFC' } });
    fireEvent.change(screen.getByLabelText(/deposit account number/i), {
      target: { value: 'FD-NEW' },
    });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    fireEvent.change(screen.getByLabelText(/interest rate/i), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/maturity date/i), { target: { value: '2026-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: /^create$/i }));

    await waitFor(() => {
      const panel = document.querySelector('.fd-form__error-panel');
      expect(panel).toBeTruthy();
      expect(panel).toHaveTextContent(/available as of investment date:/i);
      expect(panel).toHaveTextContent(/current ledger balance:/i);
      expect(panel).toHaveTextContent(/for backdated fds, record or seed bank cash/i);
    });
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('shows seed warning and zero ledger balance when opening balance is not seeded', async () => {
    api.fetchBankAccounts.mockResolvedValue([unseededBankAccount]);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));

    expect(screen.getByText(/current ledger balance:/i)).toBeInTheDocument();
    expect(screen.getByText(/reference balance \(250000/i)).toBeInTheDocument();
    expect(screen.getAllByText(/opening balance is not yet seeded into the cash ledger/i).length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    expect(screen.getByRole('button', { name: /^create$/i })).toBeDisabled();
  });

  it('shows as-of shortfall warning when principal exceeds investment-date balance', async () => {
    api.fetchBankAccountBalance.mockResolvedValue({
      bank_account_id: 10,
      currency: 'INR',
      current_balance: 250000,
      balance_as_of_date: 100000,
      as_of_date: '2024-01-01',
    });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '300000' } });

    await waitFor(() => {
      expect(screen.getByText(/available as of 2024-01-01 is/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /^create$/i })).not.toBeDisabled();
  });

  it('successful create works when investment date matches deposit date balance', async () => {
    api.fetchBankAccountBalance.mockResolvedValue({
      bank_account_id: 10,
      currency: 'INR',
      current_balance: 1109389,
      balance_as_of_date: 1109389,
      as_of_date: '2023-09-24',
    });
    api.createFixedDeposit.mockResolvedValueOnce({
      ...sampleFd,
      id: 2,
      deposit_account_number: 'FD-NEW',
    });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/institution/i), { target: { value: 'HDFC' } });
    fireEvent.change(screen.getByLabelText(/deposit account number/i), {
      target: { value: 'FD-NEW' },
    });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '1109389' } });
    fireEvent.change(screen.getByLabelText(/interest rate/i), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2023-09-24' } });
    fireEvent.change(screen.getByLabelText(/maturity date/i), { target: { value: '2024-09-24' } });
    fireEvent.click(screen.getByRole('button', { name: /^create$/i }));

    await waitFor(() => {
      expect(api.createFixedDeposit).toHaveBeenCalled();
      expect(api.createFixedDeposit.mock.calls[0][0]).toMatchObject({
        bank_account_id: 10,
        portfolio_id: 1,
      });
      expect(screen.getByText(/fixed deposit created/i)).toBeInTheDocument();
    });
  });

  it('fetches as-of balance when investment date changes', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2023-09-24' } });
    await waitFor(() => {
      expect(api.fetchBankAccountBalance).toHaveBeenCalledWith(10, { as_of: '2023-09-24' });
    });
  });

  it('legacy successful create works with seeded ledger balance', async () => {
    api.createFixedDeposit.mockResolvedValueOnce({
      ...sampleFd,
      id: 2,
      deposit_account_number: 'FD-NEW-2',
    });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/institution/i), { target: { value: 'HDFC' } });
    fireEvent.change(screen.getByLabelText(/deposit account number/i), {
      target: { value: 'FD-NEW-2' },
    });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    fireEvent.change(screen.getByLabelText(/interest rate/i), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/maturity date/i), { target: { value: '2026-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: /^create$/i }));

    await waitFor(() => {
      expect(api.createFixedDeposit).toHaveBeenCalled();
      expect(screen.getByText(/fixed deposit created/i)).toBeInTheDocument();
    });
  });

  it('disables immutable fields when opening movement exists', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /^edit$/i }));
    fireEvent.click(screen.getByRole('button', { name: /^edit$/i }));
    expect(screen.getByLabelText(/principal amount/i)).toBeDisabled();
    expect(screen.getByLabelText(/investment date/i)).toBeDisabled();
  });

  it('shows backend error when editing immutable fields', async () => {
    api.updateFixedDeposit.mockRejectedValueOnce(
      new Error('Cannot change principal_amount after the opening cash movement has been recorded.')
    );
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /^edit$/i }));
    fireEvent.click(screen.getByRole('button', { name: /^edit$/i }));
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(screen.getByText(/cannot change principal_amount/i)).toBeInTheDocument();
    });
  });

  it('opens record interest modal and validates gross/tax', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /record interest/i }));
    fireEvent.click(screen.getByRole('button', { name: /record interest/i }));

    expect(screen.getByLabelText(/gross interest/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/tax withheld/i)).toBeInTheDocument();
    expect(screen.getByText(/fd portfolio value stays principal-only/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/gross interest/i), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: /record payment/i }));
    expect(screen.getByText(/gross interest must be greater than zero/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/gross interest/i), { target: { value: '1000' } });
    fireEvent.change(screen.getByLabelText(/tax withheld/i), { target: { value: '1500' } });
    fireEvent.click(screen.getByRole('button', { name: /record payment/i }));
    expect(screen.getByText(/tax withheld cannot exceed gross interest/i)).toBeInTheDocument();
  });

  it('submits interest payment payload to backend', async () => {
    api.createFixedDepositInterestPayment.mockResolvedValueOnce({
      id: 5,
      net_interest: 900,
      warning: null,
    });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /record interest/i }));
    fireEvent.click(screen.getByRole('button', { name: /record interest/i }));
    fireEvent.change(screen.getByLabelText(/payment date/i), { target: { value: '2024-04-01' } });
    fireEvent.change(screen.getByLabelText(/gross interest/i), { target: { value: '1000' } });
    fireEvent.change(screen.getByLabelText(/tax withheld/i), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: /record payment/i }));

    await waitFor(() => {
      expect(api.createFixedDepositInterestPayment).toHaveBeenCalledWith(1, {
        payment_date: '2024-04-01',
        gross_interest: '1000',
        tax_withheld: '100',
      });
      expect(screen.getByText(/interest payment recorded/i)).toBeInTheDocument();
    });
  });

  it('shows compounded warning from backend response', async () => {
    api.createFixedDepositInterestPayment.mockResolvedValueOnce({
      id: 6,
      net_interest: 900,
      warning: 'This FD is marked compounded; periodic interest payments are unusual.',
    });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /record interest/i }));
    fireEvent.click(screen.getByRole('button', { name: /record interest/i }));
    fireEvent.change(screen.getByLabelText(/gross interest/i), { target: { value: '1000' } });
    fireEvent.click(screen.getByRole('button', { name: /record payment/i }));

    await waitFor(() => {
      expect(screen.getByText(/interest payment recorded.*compounded/i)).toBeInTheDocument();
    });
  });

  it('shows backend error on interest payment failure', async () => {
    api.createFixedDepositInterestPayment.mockRejectedValueOnce(
      new Error('Interest payments are not allowed for CLOSED fixed deposits.')
    );
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /record interest/i }));
    fireEvent.click(screen.getByRole('button', { name: /record interest/i }));
    fireEvent.change(screen.getByLabelText(/gross interest/i), { target: { value: '1000' } });
    fireEvent.click(screen.getByRole('button', { name: /record payment/i }));

    await waitFor(() => {
      expect(screen.getByText(/not allowed for closed fixed deposits/i)).toBeInTheDocument();
    });
  });

  it('reverses interest payment from expanded payments table', async () => {
    api.fetchFixedDepositInterestPayments.mockResolvedValueOnce([
      {
        id: 42,
        payment_date: '2024-04-01',
        gross_interest: 1000,
        tax_withheld: 100,
        net_interest: 900,
        currency: 'INR',
        comment: '',
        is_reversed: false,
      },
    ]);
    api.reverseFixedDepositInterestPayment.mockResolvedValueOnce({
      message: 'Fixed deposit interest payment reversed.',
    });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /interest payments/i }));
    fireEvent.click(screen.getByRole('button', { name: /interest payments/i }));

    await waitFor(() => screen.getByRole('button', { name: /reverse interest/i }));
    fireEvent.click(screen.getByRole('button', { name: /reverse interest/i }));
    expect(screen.getByText(/this debits net interest/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/reason \(required\)/i), {
      target: { value: 'Wrong quarter' },
    });
    fireEvent.click(screen.getByRole('button', { name: /confirm reversal/i }));

    await waitFor(() => {
      expect(api.reverseFixedDepositInterestPayment).toHaveBeenCalledWith(42, {
        reversal_date: expect.any(String),
        reason: 'Wrong quarter',
      });
      expect(screen.getByText(/interest payment reversed/i)).toBeInTheDocument();
    });
  });

  it('opens settlement modal with net and total display', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /settle \/ close/i }));
    fireEvent.click(screen.getByRole('button', { name: /settle \/ close/i }));

    expect(screen.getByLabelText(/settlement type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/principal returned/i).value).toBe('100000');
    fireEvent.change(screen.getByLabelText(/gross final interest/i), { target: { value: '5000' } });
    fireEvent.change(screen.getByLabelText(/tax withheld/i), { target: { value: '500' } });
    expect(screen.getByLabelText(/net interest \(display only\)/i).value).toBe('4500 INR');
    expect(screen.getByLabelText(/total net proceeds \(display only\)/i).value).toBe('104500 INR');
  });

  it('validates settlement form before submit', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /settle \/ close/i }));
    fireEvent.click(screen.getByRole('button', { name: /settle \/ close/i }));
    fireEvent.change(screen.getByLabelText(/principal returned/i), { target: { value: '0' } });
    fireEvent.change(screen.getByLabelText(/gross final interest/i), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: /record settlement/i }));

    expect(
      screen.getByText(/at least one of principal returned or net interest must be greater than zero/i)
    ).toBeInTheDocument();
  });

  it('mark matured calls API and refreshes list', async () => {
    api.markFixedDepositMatured.mockResolvedValueOnce({ ...sampleFd, status: 'MATURED' });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /mark matured/i }));
    fireEvent.click(screen.getByRole('button', { name: /mark matured/i }));

    await waitFor(() => {
      expect(api.markFixedDepositMatured).toHaveBeenCalledWith(1);
      expect(screen.getByText(/marked as matured/i)).toBeInTheDocument();
    });
  });

  it('settle success shows status message', async () => {
    api.settleFixedDeposit.mockResolvedValueOnce({
      id: 10,
      fixed_deposit_status: 'MATURED_SETTLED',
    });
    api.fetchFixedDeposits.mockResolvedValueOnce([sampleFd]).mockResolvedValueOnce([
      { ...sampleFd, status: 'MATURED_SETTLED' },
    ]);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /settle \/ close/i }));
    fireEvent.click(screen.getByRole('button', { name: /settle \/ close/i }));
    fireEvent.click(screen.getByRole('button', { name: /record settlement/i }));

    await waitFor(() => {
      expect(api.settleFixedDeposit).toHaveBeenCalled();
      expect(screen.getByText(/settlement recorded/i)).toBeInTheDocument();
    });
  });

  it('hides settlement actions for settled FD rows', async () => {
    api.fetchFixedDeposits.mockResolvedValue([
      { ...sampleFd, status: 'MATURED_SETTLED' },
      { ...sampleFd, id: 2, deposit_account_number: 'FD-002', status: 'CLOSED' },
    ]);
    renderPage();
    await waitFor(() => screen.getByText('FD-002'));

    expect(screen.queryByRole('button', { name: /settle/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /mark matured/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /record interest/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^renew$/i })).not.toBeInTheDocument();
  });

  it('shows renew action for ACTIVE and MATURED FDs', async () => {
    api.fetchFixedDeposits.mockResolvedValue([
      sampleFd,
      { ...sampleFd, id: 2, deposit_account_number: 'FD-002', status: 'MATURED' },
    ]);
    renderPage();
    await waitFor(() => screen.getByText('FD-002'));
    expect(screen.getAllByRole('button', { name: /^renew$/i })).toHaveLength(2);
  });

  it('hides renew when FD already renewed', async () => {
    api.fetchFixedDeposits.mockResolvedValue([{ ...sampleFd, has_renewal: true }]);
    renderPage();
    await waitFor(() => screen.getByText('FD-001'));
    expect(screen.queryByRole('button', { name: /^renew$/i })).not.toBeInTheDocument();
  });

  it('renew modal shows direct rollover and bank cash warnings', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /^renew$/i }));
    fireEvent.click(screen.getByRole('button', { name: /^renew$/i }));

    expect(
      screen.getByText(/directly renewed principal will not pass through the bank account/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/bank cash is still not included in portfolio value/i)
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/cash payout amount/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/net interest \(display only\)/i)).toBeInTheDocument();
  });

  it('submits renewal payload to backend', async () => {
    api.renewFixedDeposit.mockResolvedValueOnce({
      renewal_id: 3,
      old_fixed_deposit: { id: 1, status: 'MATURED_SETTLED' },
      new_fixed_deposit: { id: 4, status: 'ACTIVE' },
    });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /^renew$/i }));
    fireEvent.click(screen.getByRole('button', { name: /^renew$/i }));
    fireEvent.change(screen.getByLabelText(/new deposit account number/i), {
      target: { value: 'FD-RENEW-1' },
    });
    fireEvent.change(screen.getByLabelText(/new principal amount/i), {
      target: { value: '90000' },
    });
    fireEvent.change(screen.getByLabelText(/new interest rate/i), { target: { value: '7.5' } });
    fireEvent.change(screen.getByLabelText(/new maturity date/i), {
      target: { value: '2028-01-01' },
    });
    fireEvent.change(screen.getByLabelText(/cash payout amount/i), {
      target: { value: '10000' },
    });
    fireEvent.click(screen.getByRole('button', { name: /record renewal/i }));

    await waitFor(() => {
      expect(api.renewFixedDeposit).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          new_deposit_account_number: 'FD-RENEW-1',
          new_principal_amount: '90000',
          new_interest_rate_percent: '7.5',
          new_maturity_date: '2028-01-01',
          cash_payout_amount: '10000',
        })
      );
      expect(screen.getByText(/renewal recorded/i)).toBeInTheDocument();
    });
  });

  it('validates renewal form tax withheld', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /^renew$/i }));
    fireEvent.click(screen.getByRole('button', { name: /^renew$/i }));
    fireEvent.change(screen.getByLabelText(/new deposit account number/i), {
      target: { value: 'FD-RENEW-2' },
    });
    fireEvent.change(screen.getByLabelText(/gross interest/i), { target: { value: '1000' } });
    fireEvent.change(screen.getByLabelText(/tax withheld/i), { target: { value: '1500' } });
    fireEvent.change(screen.getByLabelText(/new maturity date/i), {
      target: { value: '2028-01-01' },
    });
    fireEvent.click(screen.getByRole('button', { name: /record renewal/i }));

    expect(screen.getByText(/tax withheld cannot exceed gross interest/i)).toBeInTheDocument();
    expect(api.renewFixedDeposit).not.toHaveBeenCalled();
  });

  it('shows Cancel FD for ledger-backed active FD', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /cancel fd/i }));
    expect(screen.queryByRole('button', { name: /^deactivate$/i })).not.toBeInTheDocument();
  });

  it('shows Deactivate for legacy FD without opening movement', async () => {
    api.fetchFixedDeposits.mockResolvedValue([
      { ...sampleFd, has_opening_cash_movement: false, opening_cash_movement_id: null },
    ]);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /^deactivate$/i }));
    expect(screen.queryByRole('button', { name: /cancel fd/i })).not.toBeInTheDocument();
  });

  it('cancel success refreshes list and shows status', async () => {
    api.cancelFixedDeposit.mockResolvedValueOnce({ ...sampleFd, status: 'CANCELLED', is_active: false });
    window.confirm = vi.fn(() => true);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /cancel fd/i }));
    fireEvent.click(screen.getByRole('button', { name: /cancel fd/i }));

    await waitFor(() => {
      expect(api.cancelFixedDeposit).toHaveBeenCalledWith(1, {});
      expect(screen.getByText(/cancelled/i)).toBeInTheDocument();
    });
  });

  it('cancel error is displayed', async () => {
    api.cancelFixedDeposit.mockRejectedValueOnce(new Error('Cannot cancel with interest payments'));
    window.confirm = vi.fn(() => true);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /cancel fd/i }));
    fireEvent.click(screen.getByRole('button', { name: /cancel fd/i }));

    await waitFor(() => {
      expect(screen.getByText(/cannot cancel with interest payments/i)).toBeInTheDocument();
    });
  });

  it('renders interest and tax report section with disclaimer', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /interest & tax report/i })).toBeInTheDocument();
    });
    const section = screen.getByRole('region', {
      name: /fixed deposit interest and tax report/i,
    });
    expect(
      within(section).getAllByText(/this report is not tax advice/i).length
    ).toBeGreaterThanOrEqual(1);
    expect(
      within(section).getByText(/reversed interest payments are excluded/i)
    ).toBeInTheDocument();
  });

  it('loads interest report with date filters and shows totals', async () => {
    api.fetchFixedDepositInterestReport.mockResolvedValueOnce({
      rows: [
        {
          source_type: 'INTEREST_PAYMENT',
          source_id: 1,
          date: '2024-04-01',
          portfolio_name: 'Default Portfolio',
          institution_name: 'HDFC',
          deposit_account_number: 'FD-001',
          bank_account_name: 'Savings',
          gross_interest: 1000,
          tax_withheld: 100,
          net_interest: 900,
          currency: 'INR',
          comment: '',
        },
      ],
      totals: {
        gross_interest: 1000,
        tax_withheld: 100,
        net_interest: 900,
        currency: 'INR',
        row_count: 1,
        fx_status: 'ok',
      },
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(api.fetchFixedDepositInterestReport).toHaveBeenCalled();
    });
    expect(await screen.findByText('Interest payment')).toBeInTheDocument();
    expect(screen.getAllByText('Gross interest').length).toBeGreaterThan(0);
  });

  it('shows interest report empty state', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/no interest rows/i)).toBeInTheDocument();
      expect(
        screen.getByText(/recorded interest payments, settlement interest, and renewal interest/i)
      ).toBeInTheDocument();
    });
  });

  it('shows interest report error state', async () => {
    api.fetchFixedDepositInterestReport.mockRejectedValueOnce(new Error('Report failed'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/report failed/i)).toBeInTheDocument();
    });
  });
});
