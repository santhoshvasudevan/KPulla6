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
import { fetchFixedDepositInterestReport } from '../api';
import { usePortfolio } from '../portfolioContext';

const SOURCE_LABELS = {
  INTEREST_PAYMENT: 'Interest payment',
  SETTLEMENT: 'Settlement',
  RENEWAL: 'Renewal',
};

function currentYearStart() {
  const y = new Date().getFullYear();
  return `${y}-01-01`;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
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
  const { apiQuery, selectedDisplayCurrency } = usePortfolio();
  const [startDate, setStartDate] = useState(currentYearStart);
  const [endDate, setEndDate] = useState(todayIso);
  const [groupBy, setGroupBy] = useState('none');
  const [report, setReport] = useState(emptyReport);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const displayCurrency = useMemo(
    () => selectedDisplayCurrency || 'EUR',
    [selectedDisplayCurrency]
  );

  const totalsCurrency = report.totals.display_currency || report.totals.currency;

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchFixedDepositInterestReport({
        ...apiQuery,
        display_currency: displayCurrency,
        start_date: startDate,
        end_date: endDate,
        group_by: groupBy,
      });
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
  }, [apiQuery, displayCurrency, startDate, endDate, groupBy]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const valueFor = (row, field) => {
    const displayField = `${field}_display`;
    if (row[displayField] != null) return row[displayField];
    return row[field];
  };

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
            Summarizes recorded FD interest and tax withheld. This is not tax advice.
          </p>
        </div>
        <Button type="button" variant="secondary" onClick={loadReport} disabled={loading}>
          Refresh
        </Button>
      </div>

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
            <option value="none">None</option>
            <option value="year">Year</option>
            <option value="portfolio">Portfolio</option>
            <option value="fd">Fixed deposit</option>
            <option value="source">Source</option>
          </select>
        </label>
      </div>

      {error ? <ErrorState message={error} onRetry={loadReport} /> : null}
      {report.warnings.map((warning) => (
        <WarningBanner key={warning} severity="warning" message={warning} className="fd-banner" />
      ))}

      {loading ? (
        <LoadingState message="Loading interest report…" />
      ) : (
        <>
          <div className="fd-interest-report__kpis">
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
          </div>

          {groupBy !== 'none' && report.grouped_totals.length > 0 ? (
            <DataTableShell
              title="Grouped totals"
              subtitle={`Grouped by ${groupBy}`}
              dense
            >
              <AppTable compact>
                <thead>
                  <tr>
                    <AppTableHeaderCell>Group</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Rows</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Gross</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Tax</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Net</AppTableHeaderCell>
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
            emptyDescription="No FD interest or tax withheld records match the current filters."
          >
            {report.rows.length > 0 ? (
              <AppTable compact className="fd-interest-report__table">
                <thead>
                  <tr>
                    <AppTableHeaderCell>Date</AppTableHeaderCell>
                    <AppTableHeaderCell>Portfolio</AppTableHeaderCell>
                    <AppTableHeaderCell>Institution / FD</AppTableHeaderCell>
                    <AppTableHeaderCell>Bank account</AppTableHeaderCell>
                    <AppTableHeaderCell>Source</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Gross</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Tax</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Net</AppTableHeaderCell>
                    <AppTableHeaderCell>Currency</AppTableHeaderCell>
                    <AppTableHeaderCell>Comment</AppTableHeaderCell>
                  </tr>
                </thead>
                <tbody>
                  {report.rows.map((row) => (
                    <tr key={`${row.source_type}-${row.source_id}`}>
                      <AppTableCell>{row.date}</AppTableCell>
                      <AppTableCell>{row.portfolio_name}</AppTableCell>
                      <AppTableCell>
                        {row.institution_name} / {row.deposit_account_number}
                      </AppTableCell>
                      <AppTableCell>{row.bank_account_name}</AppTableCell>
                      <AppTableCell>
                        {SOURCE_LABELS[row.source_type] || row.source_type}
                      </AppTableCell>
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
