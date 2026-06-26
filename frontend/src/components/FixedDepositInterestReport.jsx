import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  CurrencyValue,
  DataTableShell,
  ErrorState,
  KpiCard,
  LoadingState,
  WarningBanner,
  AppTable,
  AppTableCell,
  AppTableHeaderCell,
} from './ui';
import {
  fetchFixedDepositInterestReport,
  exportFixedDepositInterestReportCsv,
  downloadBlobFile,
} from '../api';
import { usePortfolio } from '../portfolioContext';

export const SOURCE_LABELS = {
  INTEREST_PAYMENT: 'Interest payment',
  SETTLEMENT: 'Settlement',
  RENEWAL: 'Renewal',
};

export const GROUP_BY_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'year', label: 'Year' },
  { value: 'portfolio', label: 'Portfolio' },
  { value: 'bank', label: 'Bank account' },
  { value: 'fd', label: 'Fixed deposit' },
  { value: 'source', label: 'Source' },
];

const GROUP_BY_LABELS = Object.fromEntries(
  GROUP_BY_OPTIONS.map((opt) => [opt.value, opt.label])
);

/** Default filters: current calendar year through today (FD-TAX-1A). */
export function currentYearStart() {
  const y = new Date().getFullYear();
  return `${y}-01-01`;
}

export function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function defaultReportFilters() {
  return {
    startDate: currentYearStart(),
    endDate: todayIso(),
    groupBy: 'none',
  };
}

function emptyReport() {
  return {
    rows: [],
    totals: {
      gross_interest: 0,
      tax_withheld: 0,
      net_interest: 0,
      currency: 'INR',
      display_currency: null,
      row_count: 0,
      fx_status: 'ok',
    },
    grouped_totals: [],
    warnings: [],
  };
}

export default function FixedDepositInterestReport() {
  const defaults = defaultReportFilters();
  const { apiQuery, selectedDisplayCurrency } = usePortfolio();
  const [startDate, setStartDate] = useState(defaults.startDate);
  const [endDate, setEndDate] = useState(defaults.endDate);
  const [groupBy, setGroupBy] = useState(defaults.groupBy);
  const [report, setReport] = useState(emptyReport);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  const displayCurrency = useMemo(
    () => selectedDisplayCurrency || 'EUR',
    [selectedDisplayCurrency]
  );

  const totalsCurrency = report.totals.display_currency || report.totals.currency;
  const showDisplayCurrencyColumn = Boolean(report.totals.display_currency);

  const reportQueryParams = useMemo(
    () => ({
      ...apiQuery,
      display_currency: displayCurrency,
      start_date: startDate,
      end_date: endDate,
      group_by: groupBy,
    }),
    [apiQuery, displayCurrency, startDate, endDate, groupBy]
  );

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchFixedDepositInterestReport(reportQueryParams);
      setReport({
        rows: Array.isArray(data?.rows) ? data.rows : [],
        totals: data?.totals || emptyReport().totals,
        grouped_totals: Array.isArray(data?.grouped_totals) ? data.grouped_totals : [],
        warnings: Array.isArray(data?.warnings) ? data.warnings : [],
      });
    } catch (e) {
      setReport(emptyReport());
      setError(e?.message || 'Failed to load interest report');
    } finally {
      setLoading(false);
    }
  }, [reportQueryParams]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const resetFilters = () => {
    const next = defaultReportFilters();
    setStartDate(next.startDate);
    setEndDate(next.endDate);
    setGroupBy(next.groupBy);
    setExportError('');
  };

  const handleExportCsv = async () => {
    setExporting(true);
    setExportError('');
    try {
      const { blob, filename } = await exportFixedDepositInterestReportCsv({
        ...apiQuery,
        display_currency: displayCurrency,
        start_date: startDate,
        end_date: endDate,
      });
      downloadBlobFile(blob, filename);
    } catch (e) {
      setExportError(e?.message || 'CSV export failed.');
    } finally {
      setExporting(false);
    }
  };

  const valueFor = (row, field) => {
    const displayField = `${field}_display`;
    if (row[displayField] != null) return row[displayField];
    return row[field];
  };

  const totalsWarnings = useMemo(() => {
    const messages = [...report.warnings];
    if (
      report.totals.fx_status &&
      report.totals.fx_status !== 'ok' &&
      !messages.some((m) => /fx/i.test(m))
    ) {
      messages.push(
        'Display-currency totals may be incomplete because FX rates are missing for some rows.'
      );
    }
    if (
      report.totals.currency === 'MIXED' &&
      !report.totals.display_currency &&
      !messages.some((m) => /multiple source currencies/i.test(m))
    ) {
      messages.push(
        'Multiple source currencies in report; totals are not combined. Select a display currency to convert and sum.'
      );
    }
    return messages;
  }, [report]);

  return (
    <section
      id="fd-interest-report"
      className="fd-interest-report"
      aria-label="Fixed deposit interest and tax report"
    >
      <div className="fd-interest-report__header">
        <div>
          <h2 className="fd-interest-report__title">Interest &amp; Tax report</h2>
          <p className="fd-interest-report__subtitle">
            Summarizes recorded FD interest and tax withheld from interest payments,
            settlement interest, and renewal interest. This report is not tax advice.
          </p>
        </div>
        <div className="fd-interest-report__header-actions">
          <Button
            type="button"
            variant="secondary"
            onClick={handleExportCsv}
            disabled={loading || exporting}
          >
            {exporting ? 'Exporting…' : 'Export CSV'}
          </Button>
          <Button type="button" variant="secondary" onClick={loadReport} disabled={loading}>
            Refresh
          </Button>
        </div>
      </div>

      <p className="fd-interest-report__export-hint">
        CSV export uses the current filters. This report is not tax advice.
      </p>

      <ul className="fd-interest-report__notes" aria-label="Report notes">
        <li>Reversed interest payments are excluded.</li>
        <li>Zero-interest settlement and renewal rows are excluded.</li>
        <li>
          This report summarizes recorded FD interest and tax withheld. It is not tax
          advice.
        </li>
      </ul>

      <div className="fd-interest-report__filters">
        <label className="fd-interest-report__filter">
          <span>From</span>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            aria-label="Report start date"
          />
        </label>
        <label className="fd-interest-report__filter">
          <span>To</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            aria-label="Report end date"
          />
        </label>
        <label className="fd-interest-report__filter">
          <span>Group by</span>
          <select
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value)}
            aria-label="Report grouping"
          >
            {GROUP_BY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <div className="fd-interest-report__filter fd-interest-report__filter--actions">
          <span aria-hidden="true">&nbsp;</span>
          <Button type="button" variant="ghost" onClick={resetFilters}>
            Reset filters
          </Button>
        </div>
      </div>

      {error ? <ErrorState message={error} onRetry={loadReport} /> : null}
      {exportError ? (
        <WarningBanner severity="error" message={exportError} className="fd-banner" />
      ) : null}

      {loading ? (
        <LoadingState message="Loading interest report…" />
      ) : (
        <>
          {totalsWarnings.map((warning) => (
            <WarningBanner
              key={warning}
              severity="warning"
              message={warning}
              className="fd-banner fd-interest-report__totals-warning"
            />
          ))}

          <div className="fd-interest-report__kpis" aria-label="Report totals">
            <KpiCard
              label="Gross interest"
              value={
                <CurrencyValue
                  value={report.totals.gross_interest}
                  currency={totalsCurrency}
                />
              }
              size="compact"
            />
            <KpiCard
              label="Tax withheld"
              value={
                <CurrencyValue
                  value={report.totals.tax_withheld}
                  currency={totalsCurrency}
                />
              }
              size="compact"
              variant="warning"
            />
            <KpiCard
              label="Net interest"
              value={
                <CurrencyValue
                  value={report.totals.net_interest}
                  currency={totalsCurrency}
                />
              }
              size="compact"
              variant="gain"
            />
            <KpiCard
              label="Row count"
              value={String(report.totals.row_count ?? 0)}
              size="compact"
            />
          </div>

          {groupBy !== 'none' && report.grouped_totals.length > 0 ? (
            <DataTableShell
              title="Grouped totals"
              subtitle={`Grouped by ${GROUP_BY_LABELS[groupBy] || groupBy}`}
              dense
            >
              <AppTable compact>
                <thead>
                  <tr>
                    <AppTableHeaderCell>Group</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Rows</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Gross interest</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Tax withheld</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Net interest</AppTableHeaderCell>
                  </tr>
                </thead>
                <tbody>
                  {report.grouped_totals.map((group) => (
                    <tr key={group.group_key}>
                      <AppTableCell>{group.group_label}</AppTableCell>
                      <AppTableCell numeric>{group.row_count}</AppTableCell>
                      <AppTableCell numeric>
                        <CurrencyValue
                          value={group.gross_interest}
                          currency={totalsCurrency}
                        />
                      </AppTableCell>
                      <AppTableCell numeric>
                        <CurrencyValue
                          value={group.tax_withheld}
                          currency={totalsCurrency}
                        />
                      </AppTableCell>
                      <AppTableCell numeric>
                        <CurrencyValue
                          value={group.net_interest}
                          currency={totalsCurrency}
                        />
                      </AppTableCell>
                    </tr>
                  ))}
                </tbody>
              </AppTable>
            </DataTableShell>
          ) : null}

          <DataTableShell
            title="Interest rows"
            subtitle={`${report.totals.row_count} row(s) in selected range`}
            dense
            empty={report.rows.length === 0}
            emptyTitle="No interest rows"
            emptyDescription="This report shows recorded interest payments, settlement interest, and renewal interest. Adjust the date range or record interest on your fixed deposits to see rows here."
          >
            {report.rows.length > 0 ? (
              <AppTable compact className="fd-interest-report__table">
                <thead>
                  <tr>
                    <AppTableHeaderCell>Date</AppTableHeaderCell>
                    <AppTableHeaderCell>Source</AppTableHeaderCell>
                    <AppTableHeaderCell>Portfolio</AppTableHeaderCell>
                    <AppTableHeaderCell>Bank / Institution</AppTableHeaderCell>
                    <AppTableHeaderCell>FD account</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Gross interest</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Tax withheld</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Net interest</AppTableHeaderCell>
                    <AppTableHeaderCell>Currency</AppTableHeaderCell>
                    {showDisplayCurrencyColumn ? (
                      <AppTableHeaderCell>Display currency</AppTableHeaderCell>
                    ) : null}
                    <AppTableHeaderCell>Comment</AppTableHeaderCell>
                  </tr>
                </thead>
                <tbody>
                  {report.rows.map((row) => (
                    <tr key={`${row.source_type}-${row.source_id}`}>
                      <AppTableCell>{row.date}</AppTableCell>
                      <AppTableCell>
                        {SOURCE_LABELS[row.source_type] || row.source_type}
                      </AppTableCell>
                      <AppTableCell>{row.portfolio_name}</AppTableCell>
                      <AppTableCell>
                        {row.bank_account_name}
                        {row.institution_name ? ` · ${row.institution_name}` : ''}
                      </AppTableCell>
                      <AppTableCell>{row.deposit_account_number}</AppTableCell>
                      <AppTableCell numeric>
                        <CurrencyValue
                          value={valueFor(row, 'gross_interest')}
                          currency={row.display_currency || row.currency}
                        />
                      </AppTableCell>
                      <AppTableCell numeric>
                        <CurrencyValue
                          value={valueFor(row, 'tax_withheld')}
                          currency={row.display_currency || row.currency}
                        />
                      </AppTableCell>
                      <AppTableCell numeric>
                        <CurrencyValue
                          value={valueFor(row, 'net_interest')}
                          currency={row.display_currency || row.currency}
                        />
                      </AppTableCell>
                      <AppTableCell>{row.currency}</AppTableCell>
                      {showDisplayCurrencyColumn ? (
                        <AppTableCell>{row.display_currency || '—'}</AppTableCell>
                      ) : null}
                      <AppTableCell>{row.comment || '—'}</AppTableCell>
                    </tr>
                  ))}
                </tbody>
              </AppTable>
            ) : null}
          </DataTableShell>
        </>
      )}
    </section>
  );
}
