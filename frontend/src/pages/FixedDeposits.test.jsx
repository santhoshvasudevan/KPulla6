import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import FixedDeposits from './FixedDeposits';
import FixedDepositDetail from './FixedDepositDetail';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', () => ({
  fetchFixedDeposits: vi.fn(),
  fetchFixedDepositDetail: vi.fn(),
  fetchFixedDepositMaturityEstimate: vi.fn(),
  fetchPortfolios: vi.fn(),
  seedBankAccountHistoricalBalance: vi.fn(),
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
  interest_payout_frequency: 'COMPOUNDED',
  investment_date: '2024-01-01',
  maturity_date: '2026-01-01',
  nominee_name: null,
  status: 'ACTIVE',
  is_active: true,
  has_opening_cash_movement: true,
  opening_cash_movement_id: 99,
  expected_maturity_value: 115000,
  expected_interest: 15000,
  estimated_maturity_value: 114500,
  estimated_total_interest: 14500,
  maturity_value_source: 'AUTO_ESTIMATE',
  estimate_type: 'COMPOUNDED_MATURITY',
  maturity_estimate_method: 'ANNUAL_COMPOUND_ACTUAL_365',
  maturity_estimate_method_label: 'Compounded interest, Actual/365',
};

const payoutFd = {
  ...sampleFd,
  id: 2,
  deposit_account_number: 'FD-PAYOUT',
  interest_payout_frequency: 'QUARTERLY',
  expected_maturity_value: 100000,
  estimated_maturity_value: 100000,
  expected_interest: 14000,
  estimated_total_interest: 14000,
  estimated_periodic_interest: 1750,
  maturity_value_source: 'AUTO_PRINCIPAL',
  estimate_type: 'PAYOUT_INTEREST',
  maturity_estimate_method: 'SIMPLE_PAYOUT_ACTUAL_365',
  maturity_estimate_method_label: 'Simple interest payout, Actual/365',
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
    <MemoryRouter>
      <PortfolioProvider disableFetch initialPortfolios={[{ id: 1, name: 'Default Portfolio', is_active: true }]}>
        <FixedDeposits />
      </PortfolioProvider>
    </MemoryRouter>
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
    api.fetchFixedDepositMaturityEstimate.mockResolvedValue({
      estimate_type: 'COMPOUNDED_MATURITY',
      estimated_maturity_value: 115000,
      estimated_interest: 15000,
      estimated_total_interest: 15000,
      maturity_estimate_method: 'ANNUAL_COMPOUND_ACTUAL_365',
      maturity_estimate_method_label: 'Compounded interest, Actual/365',
      warning: null,
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
      expect(screen.getByText('Compounded')).toBeInTheDocument();
      expect(screen.getByRole('status', { name: 'Active' })).toBeInTheDocument();
    });
  });

  it('blocks add fixed deposit when no portfolio exists', async () => {
    api.fetchPortfolios.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/create a portfolio before adding an fd/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /add fixed deposit/i })).toBeDisabled();
    });
  });

  it('create modal shows portfolio selector and funding copy', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    expect(
      screen.getByText(
        /choose the portfolio that will track this fd and the bank account that will fund it/i
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(/bank accounts are external funding sources/i)
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/portfolio to track this fd/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/funding bank account/i)).toBeInTheDocument();
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

  it('shows bank account warning when none exist', async () => {
    api.fetchBankAccounts.mockResolvedValue([]);
    api.fetchFixedDeposits.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText(/add a bank account before creating a bank-funded fd/i)
      ).toBeInTheDocument();
    });
  });

  it('allows create when bank account portfolio is unassigned', async () => {
    api.fetchBankAccounts.mockResolvedValueOnce([unassignedBankAccount]);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));

    expect(
      screen.queryByText(
        /link this bank account to a portfolio in settings → bank accounts before creating an fd/i
      )
    ).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^create$/i })).not.toBeDisabled();
  });

  it('shows structured backend missing portfolio error', async () => {
    const err = new api.FixedDepositApiError('Validation failed', {
      portfolio_id: ['Select the portfolio that should own this Fixed Deposit.'],
    });
    api.createFixedDeposit.mockRejectedValueOnce(err);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText('Institution'), { target: { value: 'HDFC' } });
    fireEvent.change(screen.getByLabelText(/deposit account number/i), {
      target: { value: 'FD-NEW' },
    });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    fireEvent.change(screen.getByLabelText(/interest rate/i), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/maturity date/i), { target: { value: '2026-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: /^create$/i }));

    await waitFor(() => {
      expect(screen.getByText(/validation failed|select the portfolio/i)).toBeInTheDocument();
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
    fireEvent.change(screen.getByLabelText('Institution'), { target: { value: 'HDFC' } });
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

  it('shows insufficient balance seed option with missing amount', async () => {
    api.fetchBankAccountBalance.mockResolvedValue({
      bank_account_id: 10,
      currency: 'INR',
      current_balance: 250000,
      balance_as_of_date: 50000,
      as_of_date: '2024-01-01',
    });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });

    await waitFor(() => {
      expect(
        screen.getByText(/insufficient balance on 2024-01-01/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/missing amount:/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /seed missing balance/i })).toBeInTheDocument();
    });
  });

  it('seed action sends correct payload and refreshes balance', async () => {
    api.fetchBankAccountBalance
      .mockResolvedValueOnce({
        bank_account_id: 10,
        currency: 'INR',
        current_balance: 250000,
        balance_as_of_date: 0,
        as_of_date: '2024-01-01',
      })
      .mockResolvedValueOnce({
        bank_account_id: 10,
        currency: 'INR',
        current_balance: 100000,
        balance_as_of_date: 100000,
        as_of_date: '2024-01-01',
      });
    api.seedBankAccountHistoricalBalance.mockResolvedValueOnce({
      balance_as_of_date: 100000,
      as_of_date: '2024-01-01',
      currency: 'INR',
      cash_movement: { id: 99, movement_date: '2023-12-31', amount: 100000 },
    });
    api.fetchBankAccounts.mockResolvedValue([seededBankAccount]);

    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });

    await waitFor(() => screen.getByRole('button', { name: /seed missing balance/i }));
    fireEvent.click(screen.getByRole('button', { name: /seed missing balance/i }));

    expect(screen.getByText(/creates a bank cash movement only/i)).toBeInTheDocument();
    fireEvent.submit(document.querySelector('.fd-form--seed'));

    await waitFor(() => {
      expect(api.seedBankAccountHistoricalBalance).toHaveBeenCalledWith(10, {
        date: '2023-12-31',
        amount: '100000',
        reason: 'Historical balance seed for FD creation',
        note: '',
      });
      expect(api.fetchBankAccountBalance).toHaveBeenCalledTimes(2);
      expect(screen.getByLabelText('Institution')).toHaveValue('');
    });
  });

  it('disables seed button while seeding', async () => {
    api.fetchBankAccountBalance.mockResolvedValue({
      bank_account_id: 10,
      currency: 'INR',
      current_balance: 0,
      balance_as_of_date: 0,
      as_of_date: '2024-01-01',
    });
    let resolveSeed;
    api.seedBankAccountHistoricalBalance.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSeed = resolve;
        })
    );

    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    await waitFor(() => screen.getByRole('button', { name: /seed missing balance/i }));
    fireEvent.click(screen.getByRole('button', { name: /seed missing balance/i }));
    const confirm = screen.getByRole('button', { name: /confirm seed/i });
    fireEvent.submit(document.querySelector('.fd-form--seed'));
    expect(confirm).toBeDisabled();
    resolveSeed({
      cash_movement: { id: 99, movement_date: '2023-12-31', amount: 100000 },
      currency: 'INR',
    });
    await waitFor(() => {
      expect(screen.getByText(/historical balance seeded/i)).toBeInTheDocument();
    });
  });

  it('seed failure shows inline error', async () => {
    api.fetchBankAccountBalance.mockResolvedValue({
      bank_account_id: 10,
      currency: 'INR',
      current_balance: 0,
      balance_as_of_date: 0,
      as_of_date: '2024-01-01',
    });
    api.seedBankAccountHistoricalBalance.mockRejectedValueOnce(new Error('Seed failed'));

    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    await waitFor(() => screen.getByRole('button', { name: /seed missing balance/i }));
    fireEvent.click(screen.getByRole('button', { name: /seed missing balance/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm seed/i }));

    expect(await screen.findByText(/seed failed/i)).toBeInTheDocument();
  });

  it('after sufficient balance FD submit works', async () => {
    api.fetchBankAccountBalance.mockResolvedValue({
      bank_account_id: 10,
      currency: 'INR',
      current_balance: 150000,
      balance_as_of_date: 150000,
      as_of_date: '2024-01-01',
    });
    api.createFixedDeposit.mockResolvedValueOnce({
      ...sampleFd,
      id: 2,
      deposit_account_number: 'FD-AFTER-SEED',
    });

    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText('Institution'), { target: { value: 'HDFC' } });
    fireEvent.change(screen.getByLabelText(/deposit account number/i), {
      target: { value: 'FD-AFTER-SEED' },
    });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    fireEvent.change(screen.getByLabelText(/interest rate/i), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/maturity date/i), { target: { value: '2026-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: /^create$/i }));

    await waitFor(() => {
      expect(api.createFixedDeposit).toHaveBeenCalledWith(
        expect.objectContaining({
          portfolio_id: 1,
          bank_account_id: 10,
        })
      );
      expect(screen.getByText(/fixed deposit created/i)).toBeInTheDocument();
    });
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
      expect(screen.getByText(/insufficient balance on 2024-01-01/i)).toBeInTheDocument();
      expect(screen.getByText(/missing amount:/i)).toBeInTheDocument();
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
    fireEvent.change(screen.getByLabelText('Institution'), { target: { value: 'HDFC' } });
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
    fireEvent.change(screen.getByLabelText('Institution'), { target: { value: 'HDFC' } });
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

  it('keeps investment date editable when opening movement exists', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /^edit$/i }));
    fireEvent.click(screen.getByRole('button', { name: /^edit$/i }));
    expect(screen.getByLabelText(/principal amount/i)).toBeDisabled();
    expect(screen.getByLabelText(/investment date/i)).not.toBeDisabled();
    expect(screen.getByText(/changing investment date also moves the linked fd opening/i)).toBeInTheDocument();
  });

  it('submits investment date correction for ledger-backed FD', async () => {
    api.updateFixedDeposit.mockResolvedValueOnce({
      ...sampleFd,
      investment_date: '2025-09-25',
      expected_maturity_value: 1150000,
    });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /^edit$/i }));
    fireEvent.click(screen.getByRole('button', { name: /^edit$/i }));
    fireEvent.change(screen.getByLabelText(/investment date/i), {
      target: { value: '2025-09-25' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(api.updateFixedDeposit).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          investment_date: '2025-09-25',
          use_auto_maturity_estimate: true,
        })
      );
    });
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

  it('shows compounded maturity estimate in create form when inputs are complete', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    fireEvent.change(screen.getByLabelText(/interest rate/i), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/maturity date/i), { target: { value: '2026-10-01' } });
    fireEvent.change(screen.getByLabelText(/payout frequency/i), { target: { value: 'COMPOUNDED' } });

    await waitFor(() => {
      expect(api.fetchFixedDepositMaturityEstimate).toHaveBeenCalled();
    });
    expect(screen.getByRole('heading', { name: /expected maturity value/i })).toBeInTheDocument();
    expect(screen.getByText(/estimated maturity value:/i)).toBeInTheDocument();
    expect(screen.getAllByText(/compounded interest, actual\/365/i).length).toBeGreaterThan(0);
  });

  it('shows payout interest estimate preview for quarterly FD', async () => {
    api.fetchFixedDepositMaturityEstimate.mockResolvedValueOnce({
      estimate_type: 'PAYOUT_INTEREST',
      estimated_maturity_value: 100000,
      estimated_total_interest: 14000,
      estimated_periodic_interest: 1750,
      maturity_estimate_method_label: 'Simple interest payout, Actual/365',
    });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    fireEvent.change(screen.getByLabelText(/interest rate/i), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/maturity date/i), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText(/payout frequency/i), { target: { value: 'QUARTERLY' } });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /expected interest payout/i })).toBeInTheDocument();
    });
    expect(screen.getByText(/maturity value \(principal returned\):/i)).toBeInTheDocument();
    expect(screen.getByText(/estimated periodic interest/i)).toBeInTheDocument();
    expect(screen.queryByText(/^estimated maturity value:/i)).not.toBeInTheDocument();
  });

  it('sends override maturity value only when enabled', async () => {
    api.createFixedDeposit.mockResolvedValueOnce({ ...sampleFd, id: 2 });
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.click(screen.getByRole('button', { name: /add fixed deposit/i }));
    fireEvent.change(screen.getByLabelText('Institution'), { target: { value: 'HDFC' } });
    fireEvent.change(screen.getByLabelText(/deposit account number/i), { target: { value: 'FD-NEW' } });
    fireEvent.change(screen.getByLabelText(/principal amount/i), { target: { value: '100000' } });
    fireEvent.change(screen.getByLabelText(/interest rate/i), { target: { value: '7' } });
    fireEvent.change(screen.getByLabelText(/investment date/i), { target: { value: '2024-01-01' } });
    fireEvent.change(screen.getByLabelText(/maturity date/i), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText(/payout frequency/i), { target: { value: 'COMPOUNDED' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /use bank\/institution maturity value/i }));
    fireEvent.change(screen.getByLabelText(/confirmed maturity value/i), {
      target: { value: '120000' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^create$/i }));

    await waitFor(() => {
      expect(api.createFixedDeposit).toHaveBeenCalledWith(
        expect.objectContaining({ expected_maturity_value: '120000' })
      );
    });
  });

  it('displays maturity value and source badge in holdings table for compounded FD', async () => {
    renderPage();
    await waitFor(() => screen.getByText(/115,000/i));
    expect(screen.getByText(/auto estimate/i)).toBeInTheDocument();
    expect(screen.getByText(/compounded interest/i)).toBeInTheDocument();
  });

  it('displays principal returned and interest estimate for payout FD in holdings', async () => {
    api.fetchFixedDeposits.mockResolvedValueOnce([payoutFd]);
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText(/principal returned/i).length).toBeGreaterThan(0);
    });
    expect(screen.getByText(/est\. total interest:/i)).toBeInTheDocument();
    expect(screen.getByText(/est\. quarterly payout:/i)).toBeInTheDocument();
    expect(screen.queryByText(/auto estimate/i)).not.toBeInTheDocument();
  });

  it('displays user confirmed badge when source is user confirmed', async () => {
    api.fetchFixedDeposits.mockResolvedValueOnce([
      { ...sampleFd, maturity_value_source: 'USER_CONFIRMED' },
    ]);
    renderPage();
    await waitFor(() => screen.getByText(/user confirmed/i));
  });

  it('shows maturity value for legacy compounded FD when API returns dynamic estimate', async () => {
    api.fetchFixedDeposits.mockResolvedValueOnce([
      {
        ...sampleFd,
        portfolio_name: 'IndianInvestments',
        institution_name: 'HDFC',
        principal_amount: 1109389,
        interest_rate_percent: 7.25,
        interest_payout_frequency: 'COMPOUNDED',
        investment_date: '2023-09-25',
        maturity_date: '2026-09-25',
        expected_maturity_value: 1375421.12,
        estimated_maturity_value: 1375421.12,
        expected_interest: 266032.12,
        maturity_value_source: 'AUTO_ESTIMATE',
        maturity_estimate_method_label: 'Compounded interest, Actual/365',
      },
    ]);
    renderPage();
    await waitFor(() => screen.getByText(/1,375,421/i));
    expect(screen.getByText(/auto estimate/i)).toBeInTheDocument();
    expect(screen.getByText(/compounded interest/i)).toBeInTheDocument();
  });

  it('shows not estimated fallback when maturity value unavailable', async () => {
    api.fetchFixedDeposits.mockResolvedValueOnce([
      {
        ...sampleFd,
        expected_maturity_value: null,
        estimated_maturity_value: null,
        expected_interest: null,
        maturity_value_source: 'AUTO_ESTIMATE',
        maturity_estimate_method_label: null,
      },
    ]);
    renderPage();
    await waitFor(() => screen.getByText(/not estimated/i));
  });

  it('renders FD actions in full-width action strip below row', async () => {
    renderPage();
    await waitFor(() => screen.getByTestId('fd-action-strip-1'));
    const strip = screen.getByTestId('fd-action-strip-1');
    expect(within(strip).getByRole('button', { name: /record interest/i })).toBeInTheDocument();
    expect(within(strip).getByRole('button', { name: /interest payments/i })).toBeInTheDocument();
    expect(within(strip).getByRole('button', { name: /edit/i })).toBeInTheDocument();
    expect(within(strip).getByRole('button', { name: /cancel fd/i })).toBeInTheDocument();
    expect(strip).toHaveClass('fd-action-strip');
  });

  it('action strip buttons open the same flows', async () => {
    renderPage();
    await waitFor(() => screen.getByTestId('fd-action-strip-1'));
    fireEvent.click(screen.getByRole('button', { name: /record interest/i }));
    const interestDialog = screen.getByRole('dialog');
    expect(interestDialog).toBeInTheDocument();
    fireEvent.click(within(interestDialog).getByRole('button', { name: /^cancel$/i }));

    fireEvent.click(screen.getByRole('button', { name: /^edit$/i }));
    const editDialog = screen.getByRole('dialog');
    expect(editDialog).toHaveAccessibleName(/edit fixed deposit/i);
    fireEvent.click(within(editDialog).getByRole('button', { name: /^cancel$/i }));

    fireEvent.click(screen.getByRole('button', { name: /interest payments/i }));
    await waitFor(() => {
      expect(api.fetchFixedDepositInterestPayments).toHaveBeenCalledWith(1);
    });
  });

  it('navigates to detail page when holding row is clicked', async () => {
    api.fetchFixedDepositDetail.mockResolvedValue({
      fixed_deposit: sampleFd,
      expected_interest_schedule: [],
      term_totals: {},
      detailed_calculation: { approximation_note: 'estimate' },
      financial_year_options: [],
      warnings: [],
    });
    render(
      <MemoryRouter initialEntries={['/fixed-deposits']}>
        <PortfolioProvider disableFetch initialPortfolios={[{ id: 1, name: 'Default Portfolio', is_active: true }]}>
          <Routes>
            <Route path="/fixed-deposits" element={<FixedDeposits />} />
            <Route path="/fixed-deposits/:fdId" element={<FixedDepositDetail />} />
          </Routes>
        </PortfolioProvider>
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText('HDFC'));
    fireEvent.click(screen.getByRole('link', { name: /view fixed deposit hdfc fd-001/i }));
    await waitFor(() => {
      expect(api.fetchFixedDepositDetail).toHaveBeenCalledWith('1', {});
      expect(screen.getByRole('heading', { name: /fixed deposit detail/i })).toBeInTheDocument();
    });
  });
});
