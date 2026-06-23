import { useCallback, useEffect, useState, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchTransactions,
  fetchTransactionFilterOptions,
  deleteTransaction,
  importTransactionsCsv,
  previewCsvImportCash,
  updateTransaction,
  futureImpactFromApiError,
} from '../api';
import TransactionModal from '../components/TransactionModal';
import CashFutureImpactDisplay, {
  TRANSACTION_FUTURE_IMPACT_INTRO,
  TRANSACTION_FUTURE_IMPACT_HELPER,
} from '../components/CashFutureImpactDisplay';
import '../components/CashFutureImpactDisplay.css';
import CsvImportCashPreviewModal from '../components/CsvImportCashPreviewModal';
import {
  PageHeader,
  AppCard,
  DataTableShell,
  AppTable,
  AppTableCell,
  AppTableHeaderCell,
  Button,
  LoadingState,
  ErrorState,
  EmptyState,
  WarningBanner,
  CurrencyValue,
  StatusBadge,
} from '../components/ui';
import {
  isMutualFundTransaction,
  transactionSymbolLabel,
  transactionQuantity,
  transactionUnitPrice,
  transactionLineTotal,
  navVerificationBadgeStatus,
  navVerificationLabel,
} from '../utils/transactionDisplay';
import { buildTransactionUpdatePayload } from '../utils/transactionPayload';
import { Plus, Edit2, Trash2 } from 'lucide-react';
import CashAwarePortfolioStatus from '../components/CashAwarePortfolioStatus';
import TransactionFilterBar from '../components/TransactionFilterBar';
import {
  STOCK_CSV_COLUMNS,
  MF_CSV_REQUIRED_COLUMNS,
  MF_CSV_OPTIONAL_COLUMNS,
  getSampleMutualFundCsvContent,
  downloadSampleMutualFundCsv,
} from '../utils/csvImportGuidance';
import './Transactions.css';
import { usePortfolio } from '../portfolioContext';

const PAGE_SIZE_OPTIONS = [20, 50, 100];
const DEFAULT_PAGE_SIZE = 50;

function importBannerSeverity(status) {
  if (status.startsWith('Imported')) return 'success';
  if (status.includes('failed') || status.includes('Please choose')) return 'warning';
  return 'info';
}

export default function Transactions() {
  const {
    apiQuery,
    selectedPortfolioName,
    selectedPortfolioMode,
    portfolios,
    selectedDisplayCurrency,
  } = usePortfolio();
  const activePortfolios = useMemo(
    () => (portfolios || []).filter((p) => p && p.is_active),
    [portfolios]
  );
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState(null);
  const [importStatus, setImportStatus] = useState('');
  const [importErrors, setImportErrors] = useState([]);
  const [importing, setImporting] = useState(false);
  const [csvCashPreview, setCsvCashPreview] = useState(null);
  const [csvCashPreviewFile, setCsvCashPreviewFile] = useState(null);
  const [csvCashConfirming, setCsvCashConfirming] = useState(false);
  const [cashEntryStatus, setCashEntryStatus] = useState('');
  const [deleteFutureImpact, setDeleteFutureImpact] = useState(null);
  const [deleteError, setDeleteError] = useState('');
  const fileInputRef = useRef(null);

  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkPortfolioId, setBulkPortfolioId] = useState('');
  const [bulkStatus, setBulkStatus] = useState('');
  const [bulkAssigning, setBulkAssigning] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  // Column filters.
  const [filterPortfolioId, setFilterPortfolioId] = useState('');
  const [symbolFilter, setSymbolFilter] = useState([]);
  const [dateMode, setDateMode] = useState('any'); // 'any' | 'before' | 'after' | 'between'
  const [dateValue, setDateValue] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [filterOptions, setFilterOptions] = useState({ portfolios: [], symbols: [] });

  const computedDates = useMemo(() => {
    if (dateMode === 'after') return { date_from: dateValue || null, date_to: null };
    if (dateMode === 'before') return { date_from: null, date_to: dateValue || null };
    if (dateMode === 'between') return { date_from: dateFrom || null, date_to: dateTo || null };
    return { date_from: null, date_to: null };
  }, [dateMode, dateValue, dateFrom, dateTo]);

  const dateRangeInvalid =
    dateMode === 'between' &&
    computedDates.date_from &&
    computedDates.date_to &&
    computedDates.date_from > computedDates.date_to;

  const symbolKey = symbolFilter.join(',');

  const activeFilters = useMemo(
    () => ({
      symbols: symbolFilter,
      date_from: computedDates.date_from,
      date_to: computedDates.date_to,
    }),
    [symbolFilter, computedDates]
  );

  const effectiveScope = useMemo(() => {
    if (filterPortfolioId) {
      return {
        portfolio_id: Number(filterPortfolioId),
        display_currency: selectedDisplayCurrency || 'EUR',
      };
    }
    return apiQuery;
  }, [filterPortfolioId, apiQuery, selectedDisplayCurrency]);

  const hasActiveFilters =
    Boolean(filterPortfolioId) || symbolFilter.length > 0 || dateMode !== 'any';

  const loadData = useCallback(
    (targetPage = page, targetPageSize = pageSize) => {
      if (dateRangeInvalid) return Promise.resolve(null);
      setLoading(true);
      setError('');
      return fetchTransactions(targetPage, targetPageSize, effectiveScope, activeFilters)
        .then((d) => {
          setData(d);
          setLoading(false);
          return d;
        })
        .catch((err) => {
          setError(err.message);
          setLoading(false);
          throw err;
        });
    },
    [effectiveScope, activeFilters, dateRangeInvalid, page, pageSize]
  );

  useEffect(() => {
    if (dateRangeInvalid) {
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    fetchTransactions(page, pageSize, effectiveScope, activeFilters)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    apiQuery,
    page,
    pageSize,
    filterPortfolioId,
    symbolKey,
    computedDates.date_from,
    computedDates.date_to,
    dateRangeInvalid,
  ]);

  // Distinct filter values (symbols, portfolios) for the current scope.
  useEffect(() => {
    let cancelled = false;
    fetchTransactionFilterOptions(effectiveScope)
      .then((opts) => {
        if (cancelled) return;
        setFilterOptions({
          portfolios: Array.isArray(opts?.portfolios) ? opts.portfolios : [],
          symbols: Array.isArray(opts?.symbols) ? opts.symbols : [],
        });
      })
      .catch(() => {
        if (cancelled) return;
        setFilterOptions({ portfolios: [], symbols: [] });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiQuery, filterPortfolioId]);

  useEffect(() => {
    setSelectedIds(new Set());
    setBulkStatus('');
    setPage(1);
  }, [apiQuery]);

  const handleFilterPortfolioChange = (value) => {
    setFilterPortfolioId(value);
    setPage(1);
    setSelectedIds(new Set());
  };

  const handleSymbolFilterChange = (next) => {
    setSymbolFilter(next);
    setPage(1);
    setSelectedIds(new Set());
  };

  const handleDateModeChange = (mode) => {
    setDateMode(mode);
    setPage(1);
    setSelectedIds(new Set());
  };

  const handleClearFilters = () => {
    setFilterPortfolioId('');
    setSymbolFilter([]);
    setDateMode('any');
    setDateValue('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
    setSelectedIds(new Set());
  };

  useEffect(() => {
    setSelectedIds(new Set());
  }, [page]);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const currentPage = data?.page ?? page;
  const currentPageSize = data?.page_size ?? pageSize;
  const totalPages = data?.pages ?? 1;
  const showPagination = total > currentPageSize;
  const rangeStart = total === 0 ? 0 : (currentPage - 1) * currentPageSize + 1;
  const rangeEnd = total === 0 ? 0 : Math.min(currentPage * currentPageSize, total);

  const goToPage = (nextPage) => {
    if (nextPage < 1 || (totalPages > 0 && nextPage > totalPages)) return;
    setPage(nextPage);
  };

  const handlePageSizeChange = (e) => {
    setPageSize(Number(e.target.value));
    setPage(1);
    setSelectedIds(new Set());
  };

  const refreshAfterMutation = useCallback(() => loadData(), [loadData]);
  const allVisibleSelected =
    items.length > 0 && items.every((txn) => selectedIds.has(txn.id));
  const someVisibleSelected = items.some((txn) => selectedIds.has(txn.id));

  const toggleSelectAll = () => {
    if (allVisibleSelected) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(items.map((txn) => txn.id)));
  };

  const toggleSelectRow = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBulkAssign = async () => {
    const targetId = Number(bulkPortfolioId);
    if (!targetId || selectedIds.size === 0) return;

    setBulkAssigning(true);
    setBulkStatus('');
    const selected = items.filter((txn) => selectedIds.has(txn.id));
    let succeeded = 0;
    let failed = 0;
    let firstError = '';

    for (const txn of selected) {
      try {
        const payload = buildTransactionUpdatePayload(txn, targetId);
        await updateTransaction(txn.id, payload);
        succeeded += 1;
      } catch (err) {
        failed += 1;
        if (!firstError) firstError = err.message || 'Update failed';
      }
    }

    setSelectedIds(new Set());
    setBulkAssigning(false);
    refreshAfterMutation();

    if (failed === 0) {
      setBulkStatus(`Assigned ${succeeded} transaction${succeeded === 1 ? '' : 's'} successfully.`);
    } else {
      setBulkStatus(
        `${succeeded} succeeded, ${failed} failed.${firstError ? ` ${firstError}` : ''}`
      );
    }
  };

  const handleAdd = () => {
    setEditingTransaction(null);
    setIsModalOpen(true);
  };

  const handleEdit = (txn) => {
    setEditingTransaction(txn);
    setIsModalOpen(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this transaction?')) return;
    setDeleteFutureImpact(null);
    setDeleteError('');
    try {
      await deleteTransaction(id);
      refreshAfterMutation();
    } catch (err) {
      const impact = futureImpactFromApiError(err);
      if (impact) {
        setDeleteFutureImpact(impact);
      } else {
        setDeleteError(err.message || 'Delete failed');
      }
    }
  };

  const handleModalSuccess = (result) => {
    if (result?.kind === 'cash') {
      setCashEntryStatus(result.message || 'Cash entry recorded.');
      return;
    }
    if (result?.kind === 'asset') {
      refreshAfterMutation();
      if (result.message) {
        setCashEntryStatus(result.message);
      }
      return;
    }
    refreshAfterMutation();
  };

  const handleImportClick = () => {
    setImportStatus('');
    setImportErrors([]);
    fileInputRef.current?.click();
  };

  const applyCsvImportResult = async (result) => {
    if (result.success) {
      setImportStatus(`Imported ${result.imported_count} transactions`);
      if (page !== 1) {
        setPage(1);
      } else {
        await loadData(1, pageSize);
      }
    } else {
      setImportErrors(result.errors || []);
      setImportStatus('Import failed — fix errors and try again');
    }
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setImportStatus('Please choose a .csv file');
      return;
    }
    setImporting(true);
    setImportStatus('');
    setImportErrors([]);
    setCsvCashPreview(null);
    setCsvCashPreviewFile(null);
    try {
      const portfolioId = apiQuery?.portfolio_id ?? null;
      const preview = await previewCsvImportCash(file, portfolioId);
      if (preview.row_errors?.length) {
        setImportErrors(preview.row_errors);
        setImportStatus('Import failed — fix errors and try again');
        return;
      }
      if (
        preview.cash_aware &&
        !preview.can_import_without_deposits &&
        (preview.proposed_deposits?.length || preview.shortfalls?.length)
      ) {
        setCsvCashPreview(preview);
        setCsvCashPreviewFile(file);
        return;
      }
      const result = await importTransactionsCsv(file, portfolioId);
      await applyCsvImportResult(result);
    } catch (err) {
      if (err.code === 'csv_cash_preview_required' && err.preview) {
        setCsvCashPreview(err.preview);
        setCsvCashPreviewFile(file);
        return;
      }
      setImportStatus(err.message || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  const handleCancelCsvCashPreview = () => {
    setCsvCashPreview(null);
    setCsvCashPreviewFile(null);
    setCsvCashConfirming(false);
  };

  const handleConfirmCsvCashImport = async () => {
    if (!csvCashPreviewFile) return;
    setCsvCashConfirming(true);
    setImportStatus('');
    setImportErrors([]);
    try {
      const portfolioId = apiQuery?.portfolio_id ?? null;
      const result = await importTransactionsCsv(csvCashPreviewFile, portfolioId, {
        createCashDeposits: true,
        cashPreviewConfirmed: true,
      });
      setCsvCashPreview(null);
      setCsvCashPreviewFile(null);
      await applyCsvImportResult(result);
    } catch (err) {
      setImportStatus(err.message || 'Import failed');
    } finally {
      setCsvCashConfirming(false);
    }
  };

  if (loading && !data) return <LoadingState message="Loading transactions…" />;
  if (error && !data) {
    return (
      <ErrorState
        title="Unable to load transactions"
        message={error}
        onRetry={loadData}
      />
    );
  }

  const importTarget =
    selectedPortfolioMode === 'portfolio' ? selectedPortfolioName : 'Default Portfolio';

  return (
    <div className="transactions-page">
      <PageHeader
        title="Transactions"
        subtitle={`${total} records · Source-of-truth activity ledger`}
        actions={
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="transactions-page__file-input"
              onChange={handleFileChange}
            />
            <Button variant="secondary" onClick={handleImportClick} disabled={importing}>
              {importing ? 'Importing…' : 'Import from CSV'}
            </Button>
            <Button variant="primary" onClick={handleAdd} className="transactions-page__add-btn">
              <Plus size={16} aria-hidden="true" />
              Add Transaction
            </Button>
          </>
        }
      />

      <CashAwarePortfolioStatus className="transactions-page__cash-aware" />

      <WarningBanner
        severity="info"
        message={
          <>
            Imported transactions will be added to: <strong>{importTarget}</strong>. Stock CSV:
            Action=STOCK_SPLIT uses Qty=split_from and Price/Share=split_to; SWAP rows import as
            splits.
          </>
        }
        className="transactions-page__banner"
      />

      <details className="transactions-import-help transactions-page__banner">
        <summary>Supported CSV formats</summary>
        <div className="transactions-import-help__body">
          <p className="transactions-import-help__lead">
            Use one format per file. The backend detects stock vs mutual fund from the header row.
          </p>
          <dl className="transactions-import-help__formats">
            <div>
              <dt>Stock CSV</dt>
              <dd>
                <code>{STOCK_CSV_COLUMNS}</code>
              </dd>
            </div>
            <div>
              <dt>Mutual fund CSV</dt>
              <dd>
                <code>{MF_CSV_REQUIRED_COLUMNS}</code>
                <span className="transactions-import-help__optional">
                  Optional: {MF_CSV_OPTIONAL_COLUMNS}
                </span>
              </dd>
            </div>
          </dl>
          <ul className="transactions-import-help__rules">
            <li>Do not mix stock and mutual fund rows in one CSV.</li>
            <li>MF Action supports BUY and SELL only.</li>
            <li>MF dates must be MM/DD/YY or MM/DD/YYYY.</li>
            <li>MF Currency defaults to INR when omitted.</li>
            <li>
              MF Fees: leave empty to let the backend derive fees from paid value minus market
              value.
            </li>
          </ul>
          <div className="transactions-import-help__example">
            <p className="transactions-import-help__example-label">MF example (header + one row)</p>
            <pre className="transactions-import-help__sample">
              <code>{getSampleMutualFundCsvContent().trimEnd()}</code>
            </pre>
            <Button
              type="button"
              variant="secondary"
              className="transactions-import-help__download"
              onClick={downloadSampleMutualFundCsv}
            >
              Download sample MF CSV
            </Button>
          </div>
        </div>
      </details>

      {importStatus && importErrors.length === 0 ? (
        <WarningBanner
          severity={importBannerSeverity(importStatus)}
          message={importStatus}
          className="transactions-page__banner"
        />
      ) : null}

      {importErrors.length > 0 ? (
        <div className="transactions-import-block transactions-page__banner">
          <WarningBanner
            severity="error"
            title={importStatus || 'Import failed — fix errors and try again'}
          />
          <ul className="transactions-import-errors">
            {importErrors.map((er, i) => (
              <li key={i}>
                Row {er.row}
                {er.field ? ` — ${er.field}` : ''}: {er.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {bulkStatus ? (
        <WarningBanner
          severity={bulkStatus.includes('failed') ? 'warning' : 'success'}
          message={bulkStatus}
          className="transactions-page__banner"
        />
      ) : null}

      {cashEntryStatus ? (
        <WarningBanner
          severity="success"
          message={
            <>
              {cashEntryStatus}{' '}
              <Link to="/cash" className="transactions-page__cash-link">
                View cash ledger on Cash page
              </Link>
            </>
          }
          className="transactions-page__banner"
        />
      ) : null}

      {deleteError ? (
        <WarningBanner
          severity="warning"
          message={deleteError}
          className="transactions-page__banner"
        />
      ) : null}

      {deleteFutureImpact ? (
        <div className="transactions-page__delete-impact">
          <CashFutureImpactDisplay
            impact={deleteFutureImpact}
            intro={TRANSACTION_FUTURE_IMPACT_INTRO}
            helperText={TRANSACTION_FUTURE_IMPACT_HELPER}
          />
        </div>
      ) : null}

      <AppCard
        className="transactions-page__filters"
        title="Filters"
        subtitle="Portfolio, symbol, and date constraints apply before pagination"
        compact
      >
        <TransactionFilterBar
          embedded
          portfolios={filterOptions.portfolios.length ? filterOptions.portfolios : activePortfolios}
          symbolOptions={filterOptions.symbols}
          filterPortfolioId={filterPortfolioId}
          onPortfolioChange={handleFilterPortfolioChange}
          symbolFilter={symbolFilter}
          onSymbolFilterChange={handleSymbolFilterChange}
          dateMode={dateMode}
          onDateModeChange={handleDateModeChange}
          dateValue={dateValue}
          onDateValueChange={setDateValue}
          dateFrom={dateFrom}
          onDateFromChange={setDateFrom}
          dateTo={dateTo}
          onDateToChange={setDateTo}
          dateRangeInvalid={Boolean(dateRangeInvalid)}
          hasActiveFilters={hasActiveFilters}
          onClearFilters={handleClearFilters}
        />
      </AppCard>

      {someVisibleSelected ? (
        <div className="transactions-bulk-toolbar" aria-label="Bulk actions">
          <span className="transactions-bulk-toolbar__count">
            {selectedIds.size} selected
          </span>
          <label className="transactions-bulk-toolbar__label" htmlFor="bulk-portfolio-select">
            Assign to portfolio
          </label>
          <select
            id="bulk-portfolio-select"
            aria-label="assign to portfolio"
            className="transactions-bulk-toolbar__select"
            value={bulkPortfolioId}
            onChange={(e) => setBulkPortfolioId(e.target.value)}
            disabled={bulkAssigning}
          >
            <option value="">Select portfolio…</option>
            {activePortfolios.map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.name}
              </option>
            ))}
          </select>
          <Button
            variant="primary"
            disabled={!bulkPortfolioId || bulkAssigning}
            onClick={handleBulkAssign}
          >
            {bulkAssigning ? 'Assigning…' : 'Apply'}
          </Button>
          <Button
            variant="ghost"
            disabled={bulkAssigning}
            onClick={() => setSelectedIds(new Set())}
          >
            Clear
          </Button>
        </div>
      ) : null}

      <DataTableShell
        className="transactions-page__ledger"
        title="Activity ledger"
        subtitle="Portfolio activity with type badges and right-aligned amounts"
        dense
      >
        {items.length === 0 && !loading ? (
          <EmptyState
            title="No transactions found."
            description="Add a transaction manually or import from CSV."
          />
        ) : items.length > 0 ? (
          <div
            className={`transactions-table-wrapper${loading ? ' transactions-table-wrapper--loading' : ''}`}
            aria-busy={loading}
          >
            <AppTable compact className="transactions-table">
              <thead>
                <tr>
                  <AppTableHeaderCell className="transactions-table__select-col">
                    <input
                      type="checkbox"
                      aria-label="Select all transactions on this page"
                      checked={allVisibleSelected}
                      ref={(el) => {
                        if (el) el.indeterminate = someVisibleSelected && !allVisibleSelected;
                      }}
                      onChange={toggleSelectAll}
                    />
                  </AppTableHeaderCell>
                  <AppTableHeaderCell>Portfolio</AppTableHeaderCell>
                  <AppTableHeaderCell>Symbol</AppTableHeaderCell>
                  <AppTableHeaderCell>Date</AppTableHeaderCell>
                  <AppTableHeaderCell>Type</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Qty / Units</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Price / NAV</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Fees</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Total</AppTableHeaderCell>
                  <AppTableHeaderCell>NAV status</AppTableHeaderCell>
                  <AppTableHeaderCell className="transactions-table__actions-col">
                    Actions
                  </AppTableHeaderCell>
                </tr>
              </thead>
              <tbody>
                {items.map((txn) => {
                  const isSplit = txn.type === 'STOCK_SPLIT';
                  const isMf = isMutualFundTransaction(txn);
                  const lineTotal = transactionLineTotal(txn);
                  const currency = txn.currency || (isMf ? 'INR' : 'EUR');
                  const qty = transactionQuantity(txn);
                  const unitPrice = transactionUnitPrice(txn);
                  const navStatus = txn.nav_verification_status;

                  return (
                    <tr key={txn.id} className="transactions-table__row">
                      <AppTableCell className="transactions-table__select-col">
                        <input
                          type="checkbox"
                          aria-label={`Select transaction ${txn.id}`}
                          checked={selectedIds.has(txn.id)}
                          onChange={() => toggleSelectRow(txn.id)}
                        />
                      </AppTableCell>
                      <AppTableCell>
                        {txn.portfolio_name || (txn.portfolio_id != null ? `#${txn.portfolio_id}` : '')}
                      </AppTableCell>
                      <AppTableCell className="transactions-table__symbol">
                        <div className="transactions-table__symbol-cell">
                          <span>{transactionSymbolLabel(txn)}</span>
                          {isMf && txn.folio_number ? (
                            <span className="transactions-table__folio">Folio {txn.folio_number}</span>
                          ) : null}
                        </div>
                      </AppTableCell>
                      <AppTableCell>{isMf ? txn.nav_date || txn.date : txn.date}</AppTableCell>
                      <AppTableCell>
                        <span
                          className={`ui-txn-type ui-txn-type--${String(txn.type || '').toLowerCase().replace(/_/g, '-')}`}
                        >
                          {txn.type}
                        </span>
                      </AppTableCell>
                      <AppTableCell numeric>
                        {isSplit ? `${txn.split_from}:${txn.split_to}` : qty}
                      </AppTableCell>
                      <AppTableCell numeric>
                        {isSplit || unitPrice == null ? (
                          '—'
                        ) : (
                          <CurrencyValue value={unitPrice} currency={currency} />
                        )}
                      </AppTableCell>
                      <AppTableCell numeric>
                        {isSplit ? (
                          '—'
                        ) : (
                          <CurrencyValue value={txn.fees} currency={currency} />
                        )}
                      </AppTableCell>
                      <AppTableCell numeric>
                        {isSplit || lineTotal == null ? (
                          '—'
                        ) : (
                          <CurrencyValue value={lineTotal} currency={currency} />
                        )}
                      </AppTableCell>
                      <AppTableCell>
                        {isMf && navStatus ? (
                          <StatusBadge
                            status={navVerificationBadgeStatus(navStatus)}
                            label={navVerificationLabel(navStatus)}
                          />
                        ) : (
                          '—'
                        )}
                      </AppTableCell>
                      <AppTableCell className="transactions-table__actions-col">
                        <div className="transactions-table__actions">
                          <Button
                            variant="ghost"
                            onClick={() => handleEdit(txn)}
                            title="Edit"
                            className="transactions-table__icon-btn"
                          >
                            <Edit2 size={16} aria-hidden="true" />
                          </Button>
                          <Button
                            variant="ghost"
                            onClick={() => handleDelete(txn.id)}
                            title="Delete"
                            className="transactions-table__icon-btn transactions-table__icon-btn--danger"
                          >
                            <Trash2 size={16} aria-hidden="true" />
                          </Button>
                        </div>
                      </AppTableCell>
                    </tr>
                  );
                })}
              </tbody>
            </AppTable>
          </div>
        ) : null}
      </DataTableShell>

      {total > 0 ? (
        <nav className="transactions-pagination" aria-label="Transactions pagination">
          <p className="transactions-pagination__range">
            Showing {rangeStart}–{rangeEnd} of {total}
            {showPagination ? (
              <span className="transactions-pagination__page-label">
                {' '}
                · Page {page} of {totalPages}
              </span>
            ) : null}
          </p>
          <div className="transactions-pagination__controls">
            <label className="transactions-pagination__label" htmlFor="transactions-page-size">
              Rows per page
            </label>
            <select
              id="transactions-page-size"
              className="transactions-pagination__select"
              value={pageSize}
              onChange={handlePageSizeChange}
              disabled={loading}
              aria-label="Rows per page"
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
            {showPagination ? (
              <div className="transactions-pagination__nav">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={loading || page <= 1}
                  onClick={() => goToPage(page - 1)}
                  aria-label="Previous page"
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={loading || page >= totalPages}
                  onClick={() => goToPage(page + 1)}
                  aria-label="Next page"
                >
                  Next
                </Button>
              </div>
            ) : null}
          </div>
        </nav>
      ) : null}

      <TransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleModalSuccess}
        initialData={editingTransaction}
      />

      <CsvImportCashPreviewModal
        isOpen={!!csvCashPreview}
        preview={csvCashPreview}
        confirming={csvCashConfirming}
        onConfirm={handleConfirmCsvCashImport}
        onCancel={handleCancelCsvCashPreview}
      />
    </div>
  );
}
