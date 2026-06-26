import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import FixedDepositInterestReport, {
  currentYearStart,
  defaultReportFilters,
  todayIso,
} from './FixedDepositInterestReport';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', () => ({
  fetchFixedDepositInterestReport: vi.fn(),
  exportFixedDepositInterestReportCsv: vi.fn(),
  downloadBlobFile: vi.fn(),
  getSettings: vi.fn(),
  fetchPortfolios: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

function renderReport() {
  return render(
    <PortfolioProvider disableFetch initialDisplayCurrency="INR">
      <FixedDepositInterestReport />
    </PortfolioProvider>
  );
}

const sampleRow = {
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
  comment: 'Q1 payout',
};

describe('FixedDepositInterestReport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchFixedDepositInterestReport.mockResolvedValue({
      rows: [sampleRow],
      totals: {
        gross_interest: 1000,
        tax_withheld: 100,
        net_interest: 900,
        currency: 'INR',
        display_currency: 'INR',
        row_count: 1,
        fx_status: 'ok',
      },
      grouped_totals: [],
      warnings: [],
    });
    api.exportFixedDepositInterestReportCsv.mockResolvedValue({
      blob: new Blob(['csv'], { type: 'text/csv' }),
      filename: 'fd-interest-tax.csv',
    });
  });

  it('defaults date range to current calendar year through today', async () => {
    renderReport();
    const start = screen.getByLabelText('Report start date');
    const end = screen.getByLabelText('Report end date');
    expect(start).toHaveValue(currentYearStart());
    expect(end).toHaveValue(todayIso());
    await waitFor(() => {
      expect(api.fetchFixedDepositInterestReport).toHaveBeenCalledWith(
        expect.objectContaining({
          start_date: currentYearStart(),
          end_date: todayIso(),
        })
      );
    });
  });

  it('exposes group_by bank option in selector', async () => {
    renderReport();
    const select = await screen.findByLabelText('Report grouping');
    expect(within(select).getByRole('option', { name: 'Bank account' })).toBeInTheDocument();
  });

  it('reset filters restores default date range and grouping', async () => {
    renderReport();
    await waitFor(() => expect(api.fetchFixedDepositInterestReport).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText('Report start date'), {
      target: { value: '2020-01-01' },
    });
    fireEvent.change(screen.getByLabelText('Report end date'), {
      target: { value: '2020-12-31' },
    });
    fireEvent.change(screen.getByLabelText('Report grouping'), {
      target: { value: 'bank' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Reset filters' }));

    const defaults = defaultReportFilters();
    await waitFor(() => {
      expect(screen.getByLabelText('Report start date')).toHaveValue(defaults.startDate);
      expect(screen.getByLabelText('Report end date')).toHaveValue(defaults.endDate);
      expect(screen.getByLabelText('Report grouping')).toHaveValue('none');
    });

    await waitFor(() => {
      expect(api.fetchFixedDepositInterestReport).toHaveBeenCalledWith(
        expect.objectContaining({
          start_date: defaults.startDate,
          end_date: defaults.endDate,
          group_by: 'none',
        })
      );
    });
  });

  it('shows reversed and zero-interest exclusion notes', async () => {
    renderReport();
    expect(
      await screen.findByText(/reversed interest payments are excluded/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/zero-interest settlement and renewal rows are excluded/i)
    ).toBeInTheDocument();
  });

  it('shows tax-not-advice note', async () => {
    renderReport();
    await waitFor(() => {
      expect(api.fetchFixedDepositInterestReport).toHaveBeenCalled();
    });
    const section = screen.getByRole('region', {
      name: /fixed deposit interest and tax report/i,
    });
    expect(
      within(section).getByText(
        /summarizes recorded fd interest and tax withheld from interest payments/i
      )
    ).toBeInTheDocument();
    expect(
      within(section).getAllByText(/this report is not tax advice/i).length
    ).toBeGreaterThanOrEqual(1);
    expect(
      within(section).getByText(/it is not tax advice/i)
    ).toBeInTheDocument();
  });

  it('shows FX warning near totals when API reports partial FX', async () => {
    api.fetchFixedDepositInterestReport.mockResolvedValueOnce({
      rows: [],
      totals: {
        gross_interest: 0,
        tax_withheld: 0,
        net_interest: 0,
        currency: 'INR',
        display_currency: 'EUR',
        row_count: 0,
        fx_status: 'fx_unavailable',
      },
      grouped_totals: [],
      warnings: ['FX rates are missing for some report rows; converted totals may be partial.'],
    });
    renderReport();
    expect(
      await screen.findByText(/fx rates are missing for some report rows/i)
    ).toBeInTheDocument();
  });

  it('shows mixed currency warning when totals currency is MIXED', async () => {
    api.fetchFixedDepositInterestReport.mockResolvedValueOnce({
      rows: [],
      totals: {
        gross_interest: 0,
        tax_withheld: 0,
        net_interest: 0,
        currency: 'MIXED',
        display_currency: null,
        row_count: 0,
        fx_status: 'ok',
      },
      grouped_totals: [],
      warnings: [],
    });
    renderReport();
    expect(
      await screen.findByText(/multiple source currencies in report/i)
    ).toBeInTheDocument();
  });

  it('shows improved empty state message', async () => {
    api.fetchFixedDepositInterestReport.mockResolvedValueOnce({
      rows: [],
      totals: {
        gross_interest: 0,
        tax_withheld: 0,
        net_interest: 0,
        currency: 'INR',
        row_count: 0,
        fx_status: 'ok',
      },
      grouped_totals: [],
      warnings: [],
    });
    renderReport();
    expect(await screen.findByText(/no interest rows/i)).toBeInTheDocument();
    expect(
      screen.getByText(/recorded interest payments, settlement interest, and renewal interest/i)
    ).toBeInTheDocument();
  });

  it('renders grouped totals with bank grouping labels', async () => {
    const payload = {
      rows: [sampleRow],
      totals: {
        gross_interest: 1000,
        tax_withheld: 100,
        net_interest: 900,
        currency: 'INR',
        display_currency: 'INR',
        row_count: 1,
        fx_status: 'ok',
      },
      grouped_totals: [
        {
          group_key: '10',
          group_label: 'Savings',
          gross_interest: 1000,
          tax_withheld: 100,
          net_interest: 900,
          row_count: 1,
        },
      ],
      warnings: [],
    };
    api.fetchFixedDepositInterestReport.mockResolvedValue(payload);
    renderReport();
    fireEvent.change(await screen.findByLabelText('Report grouping'), {
      target: { value: 'bank' },
    });
    await waitFor(() => {
      expect(api.fetchFixedDepositInterestReport).toHaveBeenCalledWith(
        expect.objectContaining({ group_by: 'bank' })
      );
    });
    await waitFor(() => {
      expect(screen.getByText('Grouped by Bank account')).toBeInTheDocument();
      expect(screen.getByText('Savings')).toBeInTheDocument();
    });
  });

  it('renders human-readable source labels in table', async () => {
    api.fetchFixedDepositInterestReport.mockResolvedValueOnce({
      rows: [
        sampleRow,
        {
          ...sampleRow,
          source_type: 'SETTLEMENT',
          source_id: 2,
          date: '2024-06-01',
        },
        {
          ...sampleRow,
          source_type: 'RENEWAL',
          source_id: 3,
          date: '2024-09-01',
        },
      ],
      totals: {
        gross_interest: 3000,
        tax_withheld: 300,
        net_interest: 2700,
        currency: 'INR',
        display_currency: 'INR',
        row_count: 3,
        fx_status: 'ok',
      },
      grouped_totals: [],
      warnings: [],
    });
    renderReport();
    expect(await screen.findByText('Interest payment')).toBeInTheDocument();
    expect(screen.getByText('Settlement')).toBeInTheDocument();
    expect(screen.getByText('Renewal')).toBeInTheDocument();
    expect(screen.getByText('Row count')).toBeInTheDocument();
    expect(screen.getByText('Bank / Institution')).toBeInTheDocument();
    expect(screen.getByText('FD account')).toBeInTheDocument();
  });

  it('renders Export CSV button and helper text', async () => {
    renderReport();
    expect(await screen.findByRole('button', { name: 'Export CSV' })).toBeInTheDocument();
    expect(screen.getByText(/csv export uses the current filters/i)).toBeInTheDocument();
  });

  it('exports CSV with current filters and triggers download', async () => {
    renderReport();
    await waitFor(() => expect(api.fetchFixedDepositInterestReport).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
    await waitFor(() => {
      expect(api.exportFixedDepositInterestReportCsv).toHaveBeenCalledWith(
        expect.objectContaining({
          display_currency: 'INR',
          start_date: currentYearStart(),
          end_date: todayIso(),
        })
      );
      expect(api.downloadBlobFile).toHaveBeenCalled();
    });
  });

  it('shows inline error when CSV export fails', async () => {
    api.exportFixedDepositInterestReportCsv.mockRejectedValueOnce(
      new Error('Export failed')
    );
    renderReport();
    await waitFor(() => expect(api.fetchFixedDepositInterestReport).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
    expect(await screen.findByText('Export failed')).toBeInTheDocument();
  });
});
