import { act, render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useEffect, useState } from 'react';
import FixedDepositInterestReport, {
  currentYearStart,
  defaultReportFilters,
  todayIso,
} from './FixedDepositInterestReport';
import * as api from '../api';
import { PortfolioProvider, usePortfolio } from '../portfolioContext';

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
          interest_cash_amount: 2500,
          reinvested_interest_amount: 2000,
          net_interest: 4500,
          gross_interest: 5000,
          tax_withheld: 500,
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
    expect(screen.getByRole('columnheader', { name: /paid to bank/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /reinvested/i })).toBeInTheDocument();
  });

  it('shows paid/reinvested split for renewals and Unavailable for legacy unknown', async () => {
    api.fetchFixedDepositInterestReport.mockResolvedValueOnce({
      rows: [
        {
          ...sampleRow,
          source_type: 'RENEWAL',
          source_id: 10,
          deposit_account_number: 'FD-PARTIAL',
          gross_interest: 5000,
          tax_withheld: 500,
          net_interest: 4500,
          interest_cash_amount: 2500,
          reinvested_interest_amount: 2000,
        },
        {
          ...sampleRow,
          source_type: 'RENEWAL',
          source_id: 11,
          deposit_account_number: 'FD-FULL',
          gross_interest: 5000,
          tax_withheld: 500,
          net_interest: 4500,
          interest_cash_amount: 0,
          reinvested_interest_amount: 4500,
        },
        {
          ...sampleRow,
          source_type: 'RENEWAL',
          source_id: 12,
          deposit_account_number: 'FD-LEGACY',
          gross_interest: 5000,
          tax_withheld: 500,
          net_interest: 4500,
          interest_cash_amount: null,
          reinvested_interest_amount: null,
        },
      ],
      totals: {
        gross_interest: 15000,
        tax_withheld: 1500,
        net_interest: 13500,
        currency: 'INR',
        display_currency: 'INR',
        row_count: 3,
        fx_status: 'ok',
      },
      grouped_totals: [],
      warnings: [],
    });
    renderReport();
    expect(await screen.findByText('FD-PARTIAL')).toBeInTheDocument();
    expect(screen.getByText(/2,500/)).toBeInTheDocument();
    expect(screen.getByText(/2,000/)).toBeInTheDocument();
    // Legacy unknown split → Unavailable (distinct from full-rollover confirmed ₹0)
    expect(screen.getByTestId('fd-split-unavailable-interest_cash_amount')).toBeInTheDocument();
    expect(screen.getByTestId('fd-split-unavailable-reinvested_interest_amount')).toBeInTheDocument();
    const legacyRow = screen.getByText('FD-LEGACY').closest('tr');
    const fullRolloverRow = screen.getByText('FD-FULL').closest('tr');
    expect(within(legacyRow).getAllByText('Unavailable')).toHaveLength(2);
    expect(within(fullRolloverRow).getByText('₹0.00')).toBeInTheDocument();
    expect(within(fullRolloverRow).queryByText('Unavailable')).not.toBeInTheDocument();
  });

  it('shows rollover splits in deposit currency when report totals are converted', async () => {
    api.fetchFixedDepositInterestReport.mockResolvedValueOnce({
      rows: [{
        ...sampleRow,
        source_type: 'RENEWAL',
        deposit_account_number: 'FD-INR-EUR',
        gross_interest: 5000,
        gross_interest_display: 50,
        tax_withheld: 500,
        tax_withheld_display: 5,
        net_interest: 4500,
        net_interest_display: 45,
        display_currency: 'EUR',
        interest_cash_amount: 2500,
        reinvested_interest_amount: 2000,
      }],
      totals: {
        gross_interest: 50,
        tax_withheld: 5,
        net_interest: 45,
        currency: 'EUR',
        display_currency: 'EUR',
        row_count: 1,
        fx_status: 'ok',
      },
      grouped_totals: [],
      warnings: [],
    });
    renderReport();
    const row = (await screen.findByText('FD-INR-EUR')).closest('tr');
    expect(within(row).getByText('€45.00')).toBeInTheDocument();
    expect(within(row).getByText('₹2,500.00')).toBeInTheDocument();
    expect(within(row).getByText('₹2,000.00')).toBeInTheDocument();
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

  it('keeps corrected totals when an older refresh succeeds after the latest', async () => {
    let resolveStale;
    let resolveFresh;
    api.fetchFixedDepositInterestReport
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveStale = () =>
              resolve({
                rows: [{ ...sampleRow, net_interest: 900 }],
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
                warnings: ['stale warning'],
              });
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFresh = () =>
              resolve({
                rows: [{ ...sampleRow, net_interest: 1080, gross_interest: 1200, tax_withheld: 120 }],
                totals: {
                  gross_interest: 1200,
                  tax_withheld: 120,
                  net_interest: 1080,
                  currency: 'INR',
                  display_currency: 'INR',
                  row_count: 1,
                  fx_status: 'ok',
                },
                grouped_totals: [],
                warnings: ['corrected warning'],
              });
          })
      );

    function ReportWithRevisionBump() {
      const [revision, setRevision] = useState(0);
      useEffect(() => {
        setRevision(1);
      }, []);
      return <FixedDepositInterestReport refreshRevision={revision} />;
    }

    render(
      <PortfolioProvider disableFetch initialDisplayCurrency="INR">
        <ReportWithRevisionBump />
      </PortfolioProvider>
    );

    await waitFor(() => expect(api.fetchFixedDepositInterestReport).toHaveBeenCalledTimes(2));

    await act(async () => {
      resolveFresh();
    });
    const totals = await screen.findByLabelText('Report totals');
    expect(
      within(totals).getByText('Net interest').closest('.ui-metric-card')
    ).toHaveTextContent('₹1,080.00');
    expect(await screen.findByText('corrected warning')).toBeInTheDocument();

    await act(async () => {
      resolveStale();
    });
    expect(
      within(screen.getByLabelText('Report totals')).getByText('Net interest').closest('.ui-metric-card')
    ).toHaveTextContent('₹1,080.00');
    expect(screen.getByText('corrected warning')).toBeInTheDocument();
    expect(screen.queryByText('stale warning')).not.toBeInTheDocument();
    expect(
      within(screen.getByLabelText('Report totals')).getByText('Net interest').closest('.ui-metric-card')
    ).not.toHaveTextContent('₹900.00');
  });

  it('ignores an older failure and keeps latest loading until the current request settles', async () => {
    let rejectStale;
    let resolveFresh;
    api.fetchFixedDepositInterestReport
      .mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            rejectStale = () => reject(new Error('stale report failure'));
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFresh = () =>
              resolve({
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
          })
      );

    function ReportWithRevisionBump() {
      const [revision, setRevision] = useState(0);
      useEffect(() => {
        setRevision(1);
      }, []);
      return <FixedDepositInterestReport refreshRevision={revision} />;
    }

    render(
      <PortfolioProvider disableFetch initialDisplayCurrency="INR">
        <ReportWithRevisionBump />
      </PortfolioProvider>
    );

    await waitFor(() => expect(api.fetchFixedDepositInterestReport).toHaveBeenCalledTimes(2));
    expect(screen.getByText(/loading interest report/i)).toBeInTheDocument();

    await act(async () => {
      rejectStale();
    });
    expect(screen.queryByText('stale report failure')).not.toBeInTheDocument();
    expect(screen.getByText(/loading interest report/i)).toBeInTheDocument();

    await act(async () => {
      resolveFresh();
    });
    expect(await screen.findByLabelText('Report totals')).toBeInTheDocument();
    expect(screen.queryByText('stale report failure')).not.toBeInTheDocument();
    expect(screen.queryByText(/loading interest report/i)).not.toBeInTheDocument();
  });

  it('keeps the latest filter selection when an older filter request resolves late', async () => {
    let resolveNone;
    let resolveYear;
    api.fetchFixedDepositInterestReport.mockImplementation((params) => {
      if (params.group_by === 'year') {
        return new Promise((resolve) => {
          resolveYear = () =>
            resolve({
              rows: [{ ...sampleRow, net_interest: 500 }],
              totals: {
                gross_interest: 500,
                tax_withheld: 0,
                net_interest: 500,
                currency: 'INR',
                display_currency: 'INR',
                row_count: 1,
                fx_status: 'ok',
              },
              grouped_totals: [
                {
                  group_key: '2024',
                  group_label: '2024',
                  row_count: 1,
                  gross_interest: 500,
                  tax_withheld: 0,
                  net_interest: 500,
                },
              ],
              warnings: [],
            });
        });
      }
      return new Promise((resolve) => {
        resolveNone = () =>
          resolve({
            rows: [{ ...sampleRow, net_interest: 900 }],
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
      });
    });

    renderReport();
    await waitFor(() => expect(api.fetchFixedDepositInterestReport).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText('Report grouping'), {
      target: { value: 'year' },
    });
    await waitFor(() => expect(api.fetchFixedDepositInterestReport).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText('Report grouping')).toHaveValue('year');

    await act(async () => {
      resolveYear();
    });
    expect(await screen.findByText('Grouped totals')).toBeInTheDocument();
    expect(
      within(screen.getByLabelText('Report totals')).getByText('Net interest').closest('.ui-metric-card')
    ).toHaveTextContent('₹500.00');

    await act(async () => {
      resolveNone();
    });
    expect(screen.getByLabelText('Report grouping')).toHaveValue('year');
    expect(screen.getByText('Grouped totals')).toBeInTheDocument();
    expect(
      within(screen.getByLabelText('Report totals')).getByText('Net interest').closest('.ui-metric-card')
    ).toHaveTextContent('₹500.00');
    expect(
      within(screen.getByLabelText('Report totals')).getByText('Net interest').closest('.ui-metric-card')
    ).not.toHaveTextContent('₹900.00');
  });

  it('keeps the latest portfolio selection when an older portfolio request resolves late', async () => {
    let resolveAll;
    let resolveOne;
    api.fetchFixedDepositInterestReport.mockImplementation((params) => {
      if (params.portfolio_id === 7) {
        return new Promise((resolve) => {
          resolveOne = () =>
            resolve({
              rows: [{ ...sampleRow, portfolio_name: 'Only Seven', net_interest: 250 }],
              totals: {
                gross_interest: 250,
                tax_withheld: 0,
                net_interest: 250,
                currency: 'INR',
                display_currency: 'INR',
                row_count: 1,
                fx_status: 'ok',
              },
              grouped_totals: [],
              warnings: [],
            });
        });
      }
      return new Promise((resolve) => {
        resolveAll = () =>
          resolve({
            rows: [{ ...sampleRow, net_interest: 900 }],
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
      });
    });

    function FlipPortfolioAfterMount() {
      const { selectPortfolio } = usePortfolio();
      useEffect(() => {
        void selectPortfolio(7, 'Only Seven', {
          portfolio: { id: 7, name: 'Only Seven', base_currency: 'INR' },
        });
      }, [selectPortfolio]);
      return <FixedDepositInterestReport />;
    }

    render(
      <PortfolioProvider
        disableFetch
        initialDisplayCurrency="INR"
        initialPortfolios={[{ id: 7, name: 'Only Seven', base_currency: 'INR', is_active: true }]}
      >
        <FlipPortfolioAfterMount />
      </PortfolioProvider>
    );

    await waitFor(() => expect(api.fetchFixedDepositInterestReport).toHaveBeenCalledTimes(2));
    expect(api.fetchFixedDepositInterestReport.mock.calls.some(
      ([params]) => params.portfolio_id === 7
    )).toBe(true);

    await act(async () => {
      resolveOne();
    });
    const totalsAfterFresh = await screen.findByLabelText('Report totals');
    expect(
      within(totalsAfterFresh).getByText('Net interest').closest('.ui-metric-card')
    ).toHaveTextContent('₹250.00');
    expect(screen.getByText('Only Seven')).toBeInTheDocument();

    await act(async () => {
      resolveAll();
    });
    const totalsAfterStale = screen.getByLabelText('Report totals');
    expect(
      within(totalsAfterStale).getByText('Net interest').closest('.ui-metric-card')
    ).toHaveTextContent('₹250.00');
    expect(screen.getByText('Only Seven')).toBeInTheDocument();
    expect(screen.queryByText(/₹900\.00/)).not.toBeInTheDocument();
  });
});
