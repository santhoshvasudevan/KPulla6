import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BankAccountManagement from './BankAccountManagement';
import * as api from '../api';

vi.mock('../api', () => ({
  fetchBankAccounts: vi.fn(),
  createBankAccount: vi.fn(),
  updateBankAccount: vi.fn(),
  deleteBankAccount: vi.fn(),
  seedBankAccountOpeningBalance: vi.fn(),
  fetchCashMovements: vi.fn(),
  createCashMovement: vi.fn(),
}));

describe('BankAccountManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
    api.fetchCashMovements.mockResolvedValue({ items: [], total: 0 });
  });

  it('shows ledger note and read-only balance when ledger exists', async () => {
    api.fetchBankAccounts.mockResolvedValueOnce([
      {
        id: 1,
        name: 'Savings',
        institution_name: 'HDFC',
        account_number: '123',
        currency: 'INR',
        opening_balance: 5000,
        current_balance: 1200,
        has_ledger_entries: true,
        opening_balance_seeded: true,
        balance_source: 'ledger',
        include_in_portfolio_value: false,
        is_active: true,
        comment: null,
      },
    ]);

    render(<BankAccountManagement />);

    await waitFor(() => {
      expect(
        screen.getByText(/optionally include ledger balance in portfolio value/i)
      ).toBeInTheDocument();
      expect(screen.getByText('1200')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    expect(screen.getByText(/ledger-derived — read only/i)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/include this bank cash in portfolio value/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /manual\/reference balances are not included until seeded into the ledger/i
      )
    ).toBeInTheDocument();
  });

  it('toggles include in portfolio value via API', async () => {
    const account = {
      id: 3,
      name: 'Savings',
      institution_name: 'HDFC',
      account_number: '789',
      currency: 'INR',
      opening_balance: 0,
      current_balance: 5000,
      has_ledger_entries: true,
      opening_balance_seeded: true,
      balance_source: 'ledger',
      include_in_portfolio_value: false,
      is_active: true,
      comment: null,
    };
    api.fetchBankAccounts
      .mockResolvedValueOnce([account])
      .mockResolvedValueOnce([{ ...account, include_in_portfolio_value: true }]);
    api.updateBankAccount.mockResolvedValueOnce({});

    render(<BankAccountManagement />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    fireEvent.click(screen.getByLabelText(/include this bank cash in portfolio value/i));
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(api.updateBankAccount).toHaveBeenCalledWith(3, {
        name: 'Savings',
        institution_name: 'HDFC',
        account_number: '789',
        currency: 'INR',
        opening_balance: '0',
        include_in_portfolio_value: true,
        comment: '',
      });
      expect(api.fetchBankAccounts).toHaveBeenCalledTimes(2);
    });
  });

  it('shows warning when include enabled without ledger entries', async () => {
    api.fetchBankAccounts.mockResolvedValueOnce([
      {
        id: 4,
        name: 'Empty',
        institution_name: 'SBI',
        account_number: '000',
        currency: 'INR',
        opening_balance: 1000,
        current_balance: 0,
        has_ledger_entries: false,
        opening_balance_seeded: false,
        balance_source: 'manual',
        include_in_portfolio_value: false,
        is_active: true,
        comment: null,
      },
    ]);

    render(<BankAccountManagement />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    fireEvent.click(screen.getByLabelText(/include this bank cash in portfolio value/i));

    expect(
      screen.getByText(/portfolio value will include 0 until you seed/i)
    ).toBeInTheDocument();
  });

  it('shows seed opening balance when eligible', async () => {
    api.fetchBankAccounts.mockResolvedValueOnce([
      {
        id: 2,
        name: 'NRE',
        institution_name: 'SBI',
        account_number: '456',
        currency: 'INR',
        opening_balance: 10000,
        current_balance: 0,
        has_ledger_entries: false,
        opening_balance_seeded: false,
        balance_source: 'manual',
        include_in_portfolio_value: false,
        is_active: true,
        comment: null,
      },
    ]);
    api.seedBankAccountOpeningBalance.mockResolvedValueOnce({});

    render(<BankAccountManagement />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /seed opening balance/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /seed opening balance/i }));

    await waitFor(() => {
      expect(api.seedBankAccountOpeningBalance).toHaveBeenCalledWith(2);
    });
  });

  it('refreshes movement list after seeding when account is expanded', async () => {
    const accountRow = {
      id: 2,
      name: 'NRE',
      institution_name: 'SBI',
      account_number: '456',
      currency: 'INR',
      opening_balance: 10000,
      current_balance: 0,
      has_ledger_entries: false,
      opening_balance_seeded: false,
      balance_source: 'manual',
      include_in_portfolio_value: false,
      is_active: true,
      comment: null,
    };
    const accountAfterSeed = {
      ...accountRow,
      current_balance: 10000,
      has_ledger_entries: true,
      opening_balance_seeded: true,
      balance_source: 'ledger',
    };
    api.fetchBankAccounts
      .mockResolvedValueOnce([accountRow])
      .mockResolvedValueOnce([accountAfterSeed]);
    api.seedBankAccountOpeningBalance.mockResolvedValueOnce({});
    api.fetchCashMovements
      .mockResolvedValueOnce({ items: [], total: 0 })
      .mockResolvedValueOnce({
        items: [
          {
            id: 1,
            movement_type: 'OPENING_BALANCE',
            direction: 'CREDIT',
            amount: 10000,
            movement_date: '2026-06-01',
            description: 'Opening balance seed',
            source: 'MANUAL',
            created_at: '2026-06-01T09:00:00+00:00',
          },
        ],
        total: 1,
      });

    render(<BankAccountManagement />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /view movements/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /view movements/i }));

    await waitFor(() => {
      expect(api.fetchCashMovements).toHaveBeenCalledWith({ bank_account_id: 2 });
    });

    fireEvent.click(screen.getByRole('button', { name: /seed opening balance/i }));

    await waitFor(() => {
      expect(api.fetchCashMovements).toHaveBeenCalledTimes(2);
      expect(screen.getByRole('cell', { name: 'Opening balance seed' })).toBeInTheDocument();
    });
  });
});
