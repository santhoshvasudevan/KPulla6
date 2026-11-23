import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';
import FixedDepositDetail from './FixedDepositDetail';

vi.mock('../api');

const detailPayload = {
  fixed_deposit: {
    id: 1,
    institution_name: 'HDFC',
    deposit_account_number: 'FD-001',
    portfolio_name: 'Default Portfolio',
    bank_account_name: 'Savings',
    principal_amount: 100000,
    currency: 'INR',
    interest_rate_percent: 7,
    interest_payout_frequency: 'QUARTERLY',
    investment_date: '2024-01-01',
    maturity_date: '2026-01-01',
    nominee_name: null,
    status: 'ACTIVE',
    expected_maturity_value: 100000,
    estimated_total_interest: 14000,
    estimate_type: 'PAYOUT_INTEREST',
    maturity_value_source: 'AUTO_PRINCIPAL',
    maturity_estimate_method_label: 'Simple interest payout, Actual/365',
  },
  expected_interest_schedule: [
    {
      period_index: 1,
      expected_payout_date: '2024-04-01',
      expected_gross_interest: 1750,
      status: 'OVERDUE',
      schedule_row_type: 'PAYOUT',
      matched_payment: null,
    },
    {
      period_index: 2,
      expected_payout_date: '2024-07-01',
      expected_gross_interest: 1750,
      status: 'RECORDED',
      schedule_row_type: 'PAYOUT',
      matched_payment: {
        id: 9,
        payment_date: '2024-07-01',
        gross_interest: 1750,
        tax_withheld: 175,
        net_interest: 1575,
        bank_account_name: 'Savings',
        comment: '',
      },
    },
  ],
  actual_interest_payments: [],
  financial_year_options: ['2024-25', '2025-26'],
  financial_year_summary: null,
  term_totals: {
    expected_gross_interest: 14000,
    actual_gross_interest: 1750,
    tax_withheld: 175,
    actual_net_interest: 1575,
    variance_actual_vs_expected: -12250,
  },
  detailed_calculation: {
    principal: 100000,
    interest_rate_percent: 7,
    tenure_days: 731,
    tenure_years_fractional: 2.0027,
    payout_frequency: 'QUARTERLY',
    day_count_method: 'Actual/365',
    period_generation_basis: 'Calendar payout dates by frequency',
    expected_periodic_interest: 1750,
    expected_total_interest: 14000,
    expected_maturity_value: 100000,
    approximation_note: 'This is an estimate. Banks may differ.',
  },
  warnings: [],
};

function renderDetail() {
  return render(
    <PortfolioProvider disableFetch initialPortfolios={[{ id: 1, name: 'Default Portfolio' }]}>
      <MemoryRouter initialEntries={['/fixed-deposits/1']}>
        <Routes>
          <Route path="/fixed-deposits/:fdId" element={<FixedDepositDetail />} />
        </Routes>
      </MemoryRouter>
    </PortfolioProvider>
  );
}

describe('FixedDepositDetail page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchFixedDepositDetail.mockResolvedValue(detailPayload);
    api.createFixedDepositInterestPayment.mockResolvedValue({ id: 10 });
    api.updateFixedDepositInterestPayment.mockResolvedValue({ id: 9 });
  });

  it('renders header and FD details', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /fixed deposit detail/i })).toBeInTheDocument();
    });
    expect(screen.getAllByText('HDFC').length).toBeGreaterThan(0);
    expect(screen.getAllByText('FD-001').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/expected total interest/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/net interest received/i)).toBeInTheDocument();
  });

  it('renders FY filter and schedule table', async () => {
    renderDetail();
    await waitFor(() => screen.getByLabelText(/indian financial year/i));
    expect(screen.getByRole('columnheader', { name: /expected payout/i })).toBeInTheDocument();
    expect(screen.getByText('2024-04-01')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /record actual/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /edit actual/i })).toBeInTheDocument();
  });

  it('record actual opens form with defaults and saves', async () => {
    renderDetail();
    await waitFor(() => screen.getByRole('button', { name: /record actual/i }));
    fireEvent.click(screen.getByRole('button', { name: /record actual/i }));

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByTestId('fd-interest-forecast')).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/actual credited date/i).value).toBe('2024-04-01');
    expect(within(dialog).getByLabelText(/gross interest/i).value).toBe('1750');

    fireEvent.click(within(dialog).getByRole('button', { name: /apply 10% tax/i }));
    expect(within(dialog).getByLabelText(/tax withheld/i).value).toBe('175.00');

    fireEvent.click(within(dialog).getByRole('button', { name: /^save$/i }));

    await waitFor(() => {
      expect(api.createFixedDepositInterestPayment).toHaveBeenCalledWith(
        '1',
        expect.objectContaining({
          payment_date: '2024-04-01',
          gross_interest: '1750',
          tax_withheld: '175',
          client_request_id: expect.any(String),
        })
      );
    });
  });

  it('renders detailed calculation section', async () => {
    renderDetail();
    await waitFor(() => screen.getByRole('heading', { name: /detailed calculation/i }));
    expect(screen.getAllByText(/actual\/365/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/this is an estimate/i)).toBeInTheDocument();
  });

  it('shows final payout review and resolves an open discrepancy', async () => {
    const openPayout = {
      id: 41,
      fixed_deposit_id: 1,
      status: 'CONFIRMED',
      currency: 'INR',
      suggested_net_interest: 2000,
      payment_date: '2026-01-12',
      net_interest: 1850,
      discrepancy_status: 'OPEN',
      discrepancy_amount: -150,
      resolution_comment: null,
      resolved_at: null,
    };
    const resolvedPayout = {
      ...openPayout,
      discrepancy_status: 'RESOLVED',
      resolution_comment: 'Bank deducted extra TDS.',
      resolved_at: '2026-01-20T10:00:00+00:00',
    };
    api.fetchFixedDepositDetail
      .mockResolvedValueOnce({ ...detailPayload, pending_payout: openPayout })
      .mockResolvedValue({ ...detailPayload, pending_payout: resolvedPayout });
    api.resolveFixedDepositPendingPayoutDiscrepancy.mockResolvedValue(resolvedPayout);

    renderDetail();
    const review = await screen.findByTestId('fd-payout-review');
    expect(within(review).getByText(/2,000/)).toBeInTheDocument();
    expect(within(review).getByText(/1,850/)).toBeInTheDocument();
    expect(within(review).getByText(/shortfall/)).toHaveTextContent('150');
    expect(within(review).getByText('Discrepancy open')).toBeInTheDocument();

    fireEvent.click(within(review).getByRole('button', { name: /resolve discrepancy/i }));
    const dialog = screen.getByRole('dialog', { name: /resolve payout discrepancy/i });
    fireEvent.click(within(dialog).getByRole('button', { name: /mark resolved/i }));
    expect(within(dialog).getByText(/comment is required/i)).toBeInTheDocument();
    expect(api.resolveFixedDepositPendingPayoutDiscrepancy).not.toHaveBeenCalled();

    fireEvent.change(within(dialog).getByLabelText(/resolution comment/i), {
      target: { value: '  Bank deducted extra TDS. ' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /mark resolved/i }));

    await waitFor(() => {
      expect(api.resolveFixedDepositPendingPayoutDiscrepancy).toHaveBeenCalledWith(
        41,
        'Bank deducted extra TDS.'
      );
    });
    const reloaded = await screen.findByTestId('fd-payout-review');
    await waitFor(() =>
      expect(within(reloaded).getByText('Discrepancy resolved')).toBeInTheDocument()
    );
    expect(within(reloaded).getByText(/bank deducted extra tds/i)).toBeInTheDocument();
    expect(within(reloaded).getByText(/1,850/)).toBeInTheDocument();
    expect(
      within(reloaded).queryByRole('button', { name: /resolve discrepancy/i })
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('pending final payout shows estimate without a difference', async () => {
    api.fetchFixedDepositDetail.mockResolvedValue({
      ...detailPayload,
      pending_payout: {
        id: 42,
        status: 'PENDING',
        currency: 'INR',
        suggested_net_interest: 2000,
        net_interest: null,
        discrepancy_status: 'NONE',
        discrepancy_amount: null,
      },
    });
    renderDetail();
    const review = await screen.findByTestId('fd-payout-review');
    expect(within(review).getByText(/awaiting bank credit/i)).toBeInTheDocument();
    expect(within(review).getByText(/pending confirmation/i)).toBeInTheDocument();
    expect(within(review).queryByRole('button')).not.toBeInTheDocument();
  });

  it('reloads with financial year filter', async () => {
    renderDetail();
    await waitFor(() => screen.getByLabelText(/indian financial year/i));
    fireEvent.change(screen.getByLabelText(/indian financial year/i), {
      target: { value: '2024-25' },
    });
    await waitFor(() => {
      expect(api.fetchFixedDepositDetail).toHaveBeenCalledWith('1', {
        financial_year: '2024-25',
      });
    });
  });
});
