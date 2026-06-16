import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CashMovementManagement from './CashMovementManagement';
import * as api from '../api';

vi.mock('../api', () => ({
  fetchCashMovements: vi.fn(),
  createCashMovement: vi.fn(),
}));

const sampleAccount = {
  id: 1,
  name: 'Savings',
  institution_name: 'HDFC',
  account_number: '1234567890',
  currency: 'INR',
  current_balance: 1500,
  opening_balance: 5000,
  has_ledger_entries: true,
  opening_balance_seeded: true,
  balance_source: 'ledger',
};

const sampleMovements = {
  items: [
    {
      id: 10,
      bank_account_id: 1,
      movement_type: 'MANUAL_DEPOSIT',
      direction: 'CREDIT',
      amount: 1500,
      currency: 'INR',
      movement_date: '2026-06-04',
      description: 'Salary',
      source: 'MANUAL',
      created_at: '2026-06-04T10:00:00+00:00',
    },
  ],
  total: 1,
};

describe('CashMovementManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchCashMovements.mockResolvedValue(sampleMovements);
  });

  it('lists cash movements for the selected bank account', async () => {
    render(
      <CashMovementManagement account={sampleAccount} onAccountUpdated={vi.fn()} />
    );

    await waitFor(() => {
      expect(api.fetchCashMovements).toHaveBeenCalledWith({ bank_account_id: 1 });
      expect(screen.getByText('Salary')).toBeInTheDocument();
      expect(screen.getByRole('cell', { name: '1500' })).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
  });

  it('labels FD_INTEREST movement type clearly', async () => {
    api.fetchCashMovements.mockResolvedValueOnce({
      items: [
        {
          id: 2,
          movement_date: '2024-04-01',
          movement_type: 'FD_INTEREST',
          direction: 'CREDIT',
          amount: 900,
          description: 'Q1 interest',
          source: 'SYSTEM',
          created_at: '2024-04-01T10:00:00Z',
        },
      ],
      total: 1,
    });

    render(
      <CashMovementManagement account={sampleAccount} onAccountUpdated={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('FD interest')).toBeInTheDocument();
    });
  });

  it('labels settlement movement types clearly', async () => {
    api.fetchCashMovements.mockResolvedValueOnce({
      items: [
        {
          id: 3,
          movement_date: '2026-01-01',
          movement_type: 'FD_MATURITY_PRINCIPAL',
          direction: 'CREDIT',
          amount: 100000,
          description: 'Maturity',
          source: 'SYSTEM',
          created_at: '2026-01-01T10:00:00Z',
        },
        {
          id: 4,
          movement_date: '2026-01-01',
          movement_type: 'FD_CLOSURE_INTEREST',
          direction: 'CREDIT',
          amount: 500,
          description: 'Closure interest',
          source: 'SYSTEM',
          created_at: '2026-01-01T10:00:00Z',
        },
      ],
      total: 2,
    });

    render(
      <CashMovementManagement account={sampleAccount} onAccountUpdated={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('FD maturity principal')).toBeInTheDocument();
      expect(screen.getByText('FD closure interest')).toBeInTheDocument();
    });
  });

  it('shows empty state when no movements exist', async () => {
    api.fetchCashMovements.mockResolvedValueOnce({ items: [], total: 0 });

    render(
      <CashMovementManagement account={sampleAccount} onAccountUpdated={vi.fn()} />
    );

    await waitFor(() => {
      expect(
        screen.getByText(/no cash movements recorded for this bank account yet/i)
      ).toBeInTheDocument();
    });
  });

  it('displays FD opening movement type label', async () => {
    api.fetchCashMovements.mockResolvedValueOnce({
      items: [
        {
          id: 20,
          movement_type: 'FD_OPENING',
          direction: 'DEBIT',
          amount: 100000,
          movement_date: '2024-01-01',
          description: 'Fixed deposit opening: HDFC/FD-001',
          source: 'SYSTEM',
          created_at: '2024-01-01T09:00:00+00:00',
        },
      ],
      total: 1,
    });

    render(
      <CashMovementManagement account={sampleAccount} onAccountUpdated={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('FD opening')).toBeInTheDocument();
      expect(screen.getByText('SYSTEM')).toBeInTheDocument();
    });
  });

  it('shows portfolio value exclusion note', async () => {
    render(
      <CashMovementManagement account={sampleAccount} onAccountUpdated={vi.fn()} />
    );

    await waitFor(() => {
      expect(
        screen.getByText(/bank cash is ledger-tracked but not included in portfolio value yet/i)
      ).toBeInTheDocument();
    });
  });

  it('creates MANUAL_DEPOSIT without sending direction', async () => {
    const onAccountUpdated = vi.fn().mockResolvedValue(undefined);
    api.createCashMovement.mockResolvedValueOnce({ id: 11 });

    render(
      <CashMovementManagement account={sampleAccount} onAccountUpdated={onAccountUpdated} />
    );

    await waitFor(() => screen.getByRole('button', { name: /record movement/i }));

    fireEvent.click(screen.getByRole('button', { name: /record movement/i }));
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '500' } });
    fireEvent.change(screen.getByLabelText(/movement date/i), { target: { value: '2026-06-05' } });
    fireEvent.click(screen.getByRole('button', { name: /save movement/i }));

    await waitFor(() => {
      expect(api.createCashMovement).toHaveBeenCalledWith({
        bank_account_id: 1,
        movement_type: 'MANUAL_DEPOSIT',
        amount: '500',
        movement_date: '2026-06-05',
      });
      expect(onAccountUpdated).toHaveBeenCalled();
    });
  });

  it('creates MANUAL_WITHDRAWAL', async () => {
    api.createCashMovement.mockResolvedValueOnce({ id: 12 });

    render(
      <CashMovementManagement account={sampleAccount} onAccountUpdated={vi.fn()} />
    );

    await waitFor(() => screen.getByRole('button', { name: /record movement/i }));

    fireEvent.click(screen.getByRole('button', { name: /record movement/i }));
    fireEvent.change(screen.getByLabelText(/movement type/i), {
      target: { value: 'MANUAL_WITHDRAWAL' },
    });
    expect(screen.getByText(/DEBIT \(fixed for this movement type\)/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: /save movement/i }));

    await waitFor(() => {
      expect(api.createCashMovement).toHaveBeenCalledWith(
        expect.objectContaining({
          movement_type: 'MANUAL_WITHDRAWAL',
          amount: '100',
        })
      );
      expect(api.createCashMovement.mock.calls[0][0]).not.toHaveProperty('direction');
    });
  });

  it('creates ADJUSTMENT with user-selected direction', async () => {
    api.createCashMovement.mockResolvedValueOnce({ id: 13 });

    render(
      <CashMovementManagement account={sampleAccount} onAccountUpdated={vi.fn()} />
    );

    await waitFor(() => screen.getByRole('button', { name: /record movement/i }));

    fireEvent.click(screen.getByRole('button', { name: /record movement/i }));
    fireEvent.change(screen.getByLabelText(/movement type/i), {
      target: { value: 'ADJUSTMENT' },
    });
    fireEvent.change(screen.getByLabelText(/direction/i), { target: { value: 'DEBIT' } });
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '25' } });
    fireEvent.click(screen.getByRole('button', { name: /save movement/i }));

    await waitFor(() => {
      expect(api.createCashMovement).toHaveBeenCalledWith(
        expect.objectContaining({
          movement_type: 'ADJUSTMENT',
          direction: 'DEBIT',
          amount: '25',
        })
      );
    });
  });

  it('displays backend validation error for overdraft', async () => {
    api.createCashMovement.mockRejectedValueOnce(
      new Error('Insufficient bank balance for this withdrawal.')
    );

    render(
      <CashMovementManagement account={sampleAccount} onAccountUpdated={vi.fn()} />
    );

    await waitFor(() => screen.getByRole('button', { name: /record movement/i }));

    fireEvent.click(screen.getByRole('button', { name: /record movement/i }));
    fireEvent.change(screen.getByLabelText(/movement type/i), {
      target: { value: 'MANUAL_WITHDRAWAL' },
    });
    fireEvent.change(screen.getByLabelText(/amount/i), { target: { value: '99999' } });
    fireEvent.click(screen.getByRole('button', { name: /save movement/i }));

    await waitFor(() => {
      expect(screen.getByText(/insufficient bank balance/i)).toBeInTheDocument();
    });
  });

  it('reloads movements when refreshKey changes', async () => {
    const { rerender } = render(
      <CashMovementManagement
        account={sampleAccount}
        onAccountUpdated={vi.fn()}
        refreshKey={0}
      />
    );

    await waitFor(() => expect(api.fetchCashMovements).toHaveBeenCalledTimes(1));

    rerender(
      <CashMovementManagement
        account={sampleAccount}
        onAccountUpdated={vi.fn()}
        refreshKey={1}
      />
    );

    await waitFor(() => expect(api.fetchCashMovements).toHaveBeenCalledTimes(2));
  });
});
