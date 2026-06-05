import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  fetchCashBalances,
  fetchCashLedger,
  createCashDeposit,
  createCashWithdrawal,
  updateCashLedgerEntry,
  deleteCashLedgerEntry,
  CashApiError,
} from '../api';
import { usePortfolio } from '../portfolioContext';
import { SUPPORTED_CASH_CURRENCIES } from '../constants/cashCurrencies';
import {
  amountTone,
  cashEntryTypeLabel,
  isManualEditableCashEntry,
  LEDGER_ENTRY_TYPE_OPTIONS,
} from '../utils/cashDisplay';
import { Edit2, Trash2 } from 'lucide-react';
import {
  PageHeader,
  SectionCard,
  Button,
  LoadingState,
  ErrorState,
  EmptyState,
  WarningBanner,
  CurrencyValue,
} from '../components/ui';
import CashAwarePortfolioStatus from '../components/CashAwarePortfolioStatus';
import CashBackfillWizard from '../components/CashBackfillWizard';
import CashFutureImpactDisplay from '../components/CashFutureImpactDisplay';
import '../components/CashFutureImpactDisplay.css';
import '../components/TransactionModal.css';
import './Cash.css';

const LEDGER_PAGE_SIZE = 20;

function emptyEntryForm(defaultPortfolioId = '') {
  return {
    portfolio_id: defaultPortfolioId,
    date: new Date().toISOString().split('T')[0],
    currency: 'EUR',
    amount: '',
    source_of_funds: '',
    note: '',
  };
}

function formFromLedgerEntry(entry) {
  const absAmount = entry?.amount != null ? Math.abs(Number(entry.amount)) : '';
  return {
    portfolio_id: entry?.portfolio_id != null ? String(entry.portfolio_id) : '',
    date: entry?.date || new Date().toISOString().split('T')[0],
    currency: entry?.currency || 'EUR',
    amount: absAmount === '' || Number.isNaN(absAmount) ? '' : String(absAmount),
    source_of_funds: entry?.source_of_funds || '',
    note: entry?.note || '',
  };
}

function CashEntryModal({
  mode,
  open,
  onClose,
  activePortfolios,
  requirePortfolioPick,
  defaultPortfolioId,
  editingEntry,
  onSuccess,
}) {
  const isEdit = Boolean(editingEntry);
  const effectiveMode =
    isEdit && editingEntry?.entry_type === 'CASH_WITHDRAWAL' ? 'withdrawal' : mode;

  const [form, setForm] = useState(() => emptyEntryForm(defaultPortfolioId));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [shortfall, setShortfall] = useState(null);
  const [futureImpact, setFutureImpact] = useState(null);

  useEffect(() => {
    if (!open) return;
    setForm(
      isEdit ? formFromLedgerEntry(editingEntry) : emptyEntryForm(defaultPortfolioId)
    );
    setError('');
    setShortfall(null);
    setFutureImpact(null);
    setSubmitting(false);
  }, [open, defaultPortfolioId, mode, isEdit, editingEntry]);

  if (!open) return null;

  const title = isEdit
    ? effectiveMode === 'deposit'
      ? 'Edit deposit'
      : 'Edit withdrawal'
    : effectiveMode === 'deposit'
      ? 'Add deposit'
      : 'Add withdrawal';
  const submitLabel = isEdit
    ? 'Save changes'
    : effectiveMode === 'deposit'
      ? 'Record deposit'
      : 'Record withdrawal';

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setShortfall(null);
    setFutureImpact(null);

    if (!isEdit) {
      const portfolioId = Number(form.portfolio_id);
      if (!portfolioId || Number.isNaN(portfolioId)) {
        setError('Select a portfolio.');
        return;
      }
    }

    const amount = parseFloat(form.amount);
    if (!form.amount || Number.isNaN(amount) || amount <= 0) {
      setError('Enter an amount greater than zero.');
      return;
    }

    const writePayload = {
      date: form.date,
      currency: form.currency,
      amount,
      note: form.note || '',
      source_of_funds: form.source_of_funds || '',
    };

    setSubmitting(true);
    try {
      if (isEdit) {
        await updateCashLedgerEntry(editingEntry.id, writePayload);
        onSuccess(
          effectiveMode === 'deposit' ? 'Deposit updated.' : 'Withdrawal updated.'
        );
      } else {
        const createPayload = {
          ...writePayload,
          portfolio_id: Number(form.portfolio_id),
        };
        if (effectiveMode === 'deposit') {
          await createCashDeposit(createPayload);
          onSuccess('Deposit recorded.');
        } else {
          await createCashWithdrawal(createPayload);
          onSuccess('Withdrawal recorded.');
        }
      }
      onClose();
    } catch (err) {
      if (err instanceof CashApiError && err.required != null) {
        setError('Insufficient cash balance for withdrawal.');
        setShortfall({
          required: err.required,
          available: err.available,
          shortfall: err.shortfall,
          currency: err.currency,
        });
      } else if (err?.earliest_negative_date) {
        setError(err.detail || err.message);
        setFutureImpact({
          detail: err.detail,
          currency: err.currency,
          earliest_negative_date: err.earliest_negative_date,
          lowest_balance: err.lowest_balance,
          affected_entries: err.affected_entries,
        });
      } else {
        setError(err.message || 'Request failed.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-content cash-entry-modal"
        role="dialog"
        aria-labelledby="cash-entry-modal-title"
        onClick={(ev) => ev.stopPropagation()}
      >
        <h3 id="cash-entry-modal-title">{title}</h3>
        <form onSubmit={handleSubmit}>
          {isEdit && editingEntry?.portfolio_name ? (
            <div className="form-group">
              <label>Portfolio</label>
              <p>{editingEntry.portfolio_name}</p>
            </div>
          ) : null}
          {!isEdit && (requirePortfolioPick || activePortfolios.length > 1) ? (
            <div className="form-group">
              <label htmlFor="cash-entry-portfolio">Portfolio</label>
              <select
                id="cash-entry-portfolio"
                value={form.portfolio_id}
                onChange={(e) => updateField('portfolio_id', e.target.value)}
              >
                <option value="">Select portfolio…</option>
                {activePortfolios.map((p) => (
                  <option key={p.id} value={String(p.id)}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          ) : !isEdit && activePortfolios.length === 1 ? (
            <div className="form-group">
              <label>Portfolio</label>
              <p>{activePortfolios[0].name}</p>
            </div>
          ) : null}

          <div className="form-group">
            <label htmlFor="cash-entry-date">Date</label>
            <input
              id="cash-entry-date"
              type="date"
              value={form.date}
              onChange={(e) => updateField('date', e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="cash-entry-currency">Currency</label>
            <select
              id="cash-entry-currency"
              value={form.currency}
              onChange={(e) => updateField('currency', e.target.value)}
              required
            >
              {SUPPORTED_CASH_CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="cash-entry-amount">Amount</label>
            <input
              id="cash-entry-amount"
              type="number"
              min="0"
              step="0.01"
              value={form.amount}
              onChange={(e) => updateField('amount', e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="cash-entry-source">Source of funds</label>
            <input
              id="cash-entry-source"
              type="text"
              value={form.source_of_funds}
              onChange={(e) => updateField('source_of_funds', e.target.value)}
              placeholder="Optional"
            />
          </div>

          <div className="form-group">
            <label htmlFor="cash-entry-note">Note</label>
            <textarea
              id="cash-entry-note"
              rows={2}
              value={form.note}
              onChange={(e) => updateField('note', e.target.value)}
              placeholder="Optional"
            />
          </div>

          {error ? <p className="cash-entry-modal__error">{error}</p> : null}

          {futureImpact ? (
            <CashFutureImpactDisplay
              impact={futureImpact}
              className="cash-entry-modal__future-impact"
            />
          ) : null}

          {shortfall ? (
            <div className="cash-entry-modal__shortfall">
              <p>
                Required:{' '}
                <CurrencyValue value={shortfall.required} currency={shortfall.currency} />
              </p>
              <p>
                Available:{' '}
                <CurrencyValue value={shortfall.available} currency={shortfall.currency} />
              </p>
              <p>
                Shortfall:{' '}
                <CurrencyValue value={shortfall.shortfall} currency={shortfall.currency} tone="loss" />
              </p>
            </div>
          ) : null}

          <div className="cash-entry-modal__actions">
            <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? 'Saving…' : submitLabel}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Cash() {
  const {
    apiQuery,
    selectedPortfolioMode,
    selectedPortfolioId,
    selectedPortfolioName,
    portfolios,
    settingsLoaded,
  } = usePortfolio();

  const activePortfolios = useMemo(
    () => (portfolios || []).filter((p) => p && p.is_active),
    [portfolios]
  );

  const [balancesData, setBalancesData] = useState(null);
  const [ledgerData, setLedgerData] = useState(null);
  const [balancesLoading, setBalancesLoading] = useState(true);
  const [ledgerLoading, setLedgerLoading] = useState(true);
  const [balancesError, setBalancesError] = useState('');
  const [ledgerError, setLedgerError] = useState('');
  const [ledgerFutureImpact, setLedgerFutureImpact] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');

  const [depositOpen, setDepositOpen] = useState(false);
  const [withdrawalOpen, setWithdrawalOpen] = useState(false);
  const [backfillOpen, setBackfillOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState(null);

  const [filterCurrency, setFilterCurrency] = useState('');
  const [filterEntryType, setFilterEntryType] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [ledgerPage, setLedgerPage] = useState(1);

  const isAllScope = selectedPortfolioMode === 'all';
  const defaultPortfolioId =
    selectedPortfolioMode === 'portfolio' && selectedPortfolioId != null
      ? String(selectedPortfolioId)
      : '';

  const cashQueryParams = useMemo(() => {
    if (!apiQuery) return null;
    return apiQuery;
  }, [apiQuery]);

  const ledgerFilters = useMemo(
    () => ({
      currency: filterCurrency || undefined,
      entry_type: filterEntryType || undefined,
      date_from: filterDateFrom || undefined,
      date_to: filterDateTo || undefined,
    }),
    [filterCurrency, filterEntryType, filterDateFrom, filterDateTo]
  );

  const dateRangeInvalid =
    filterDateFrom && filterDateTo && filterDateFrom > filterDateTo;

  const loadBalances = useCallback(() => {
    if (!cashQueryParams) return Promise.resolve(null);
    setBalancesLoading(true);
    setBalancesError('');
    return fetchCashBalances(cashQueryParams)
      .then((data) => {
        setBalancesData(data);
        setBalancesLoading(false);
        return data;
      })
      .catch((err) => {
        setBalancesError(err.message);
        setBalancesLoading(false);
        throw err;
      });
  }, [cashQueryParams]);

  const loadLedger = useCallback(
    (page = ledgerPage) => {
      if (!cashQueryParams || dateRangeInvalid) return Promise.resolve(null);
      setLedgerLoading(true);
      setLedgerError('');
      return fetchCashLedger({
        ...cashQueryParams,
        ...ledgerFilters,
        page,
        page_size: LEDGER_PAGE_SIZE,
      })
        .then((data) => {
          setLedgerData(data);
          setLedgerLoading(false);
          return data;
        })
        .catch((err) => {
          setLedgerError(err.message);
          setLedgerLoading(false);
          throw err;
        });
    },
    [cashQueryParams, ledgerFilters, ledgerPage, dateRangeInvalid]
  );

  const refreshAll = useCallback(() => {
    return Promise.all([loadBalances(), loadLedger(ledgerPage)]);
  }, [loadBalances, loadLedger, ledgerPage]);

  useEffect(() => {
    if (!settingsLoaded || !cashQueryParams) return undefined;
    let cancelled = false;
    setBalancesLoading(true);
    fetchCashBalances(cashQueryParams)
      .then((data) => {
        if (cancelled) return;
        setBalancesData(data);
        setBalancesLoading(false);
        setBalancesError('');
      })
      .catch((err) => {
        if (cancelled) return;
        setBalancesError(err.message);
        setBalancesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cashQueryParams, settingsLoaded]);

  useEffect(() => {
    if (!settingsLoaded || !cashQueryParams || dateRangeInvalid) {
      if (dateRangeInvalid) setLedgerLoading(false);
      return undefined;
    }
    let cancelled = false;
    setLedgerLoading(true);
    fetchCashLedger({
      ...cashQueryParams,
      ...ledgerFilters,
      page: ledgerPage,
      page_size: LEDGER_PAGE_SIZE,
    })
      .then((data) => {
        if (cancelled) return;
        setLedgerData(data);
        setLedgerLoading(false);
        setLedgerError('');
      })
      .catch((err) => {
        if (cancelled) return;
        setLedgerError(err.message);
        setLedgerLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cashQueryParams, settingsLoaded, ledgerFilters, ledgerPage, dateRangeInvalid]);

  useEffect(() => {
    setLedgerPage(1);
  }, [filterCurrency, filterEntryType, filterDateFrom, filterDateTo, apiQuery]);

  const handleEntrySuccess = (message) => {
    setStatusMessage(message);
    refreshAll();
  };

  const handleDeleteEntry = async (entry) => {
    const label = cashEntryTypeLabel(entry.entry_type).toLowerCase();
    const confirmed = window.confirm(
      `Delete this ${label}? This will update cash balances.`
    );
    if (!confirmed) return;
    setStatusMessage('');
    setLedgerError('');
    setLedgerFutureImpact(null);
    try {
      await deleteCashLedgerEntry(entry.id);
      handleEntrySuccess('Cash entry deleted.');
    } catch (err) {
      setStatusMessage('');
      if (err?.earliest_negative_date) {
        setLedgerFutureImpact({
          detail: err.detail || err.message,
          currency: err.currency,
          earliest_negative_date: err.earliest_negative_date,
          lowest_balance: err.lowest_balance,
          affected_entries: err.affected_entries,
        });
      } else {
        setLedgerError(err.message || 'Could not delete cash entry.');
      }
    }
  };

  const openEditModal = (entry) => {
    setEditingEntry(entry);
    if (entry.entry_type === 'CASH_WITHDRAWAL') {
      setWithdrawalOpen(true);
    } else {
      setDepositOpen(true);
    }
  };

  const closeEntryModals = () => {
    setDepositOpen(false);
    setWithdrawalOpen(false);
    setEditingEntry(null);
  };

  if (!settingsLoaded) {
    return <LoadingState message="Loading cash…" />;
  }

  const balanceRows = balancesData?.balances ?? [];
  const totalsByCurrency = balancesData?.totals_by_currency ?? [];
  const showPortfolioColumn = isAllScope || balancesData?.portfolio_scope === 'all';
  const ledgerItems = ledgerData?.items ?? [];
  const ledgerPages = ledgerData?.pages ?? 1;

  const renderBalancesBody = () => {
    if (balancesLoading && !balancesData) {
      return <LoadingState message="Loading balances…" />;
    }
    if (balancesError) {
      return <ErrorState title="Could not load balances" message={balancesError} />;
    }
    if (balanceRows.length === 0) {
      return (
        <EmptyState
          title="No cash balances"
          description="Record a deposit to add cash in a portfolio currency."
        />
      );
    }

    return (
      <>
        <div className="cash-balances-table-wrapper">
          <table className="cash-balances-table">
            <thead>
              <tr>
                {showPortfolioColumn ? <th>Portfolio</th> : null}
                <th>Currency</th>
                <th className="num-col">Balance</th>
              </tr>
            </thead>
            <tbody>
              {balanceRows.map((row) => {
                const key = showPortfolioColumn
                  ? `${row.portfolio_id}-${row.currency}`
                  : row.currency;
                const portfolioLabel =
                  row.portfolio_name ||
                  (row.portfolio_id != null ? `#${row.portfolio_id}` : '');
                return (
                  <tr key={key}>
                    {showPortfolioColumn ? <td>{portfolioLabel}</td> : null}
                    <td>{row.currency}</td>
                    <td className="num-col">
                      <CurrencyValue value={row.balance} currency={row.currency} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {totalsByCurrency.length > 0 ? (
          <div className="cash-balances-totals">
            <p className="cash-balances-totals__title">Totals by currency</p>
            <ul className="cash-balances-totals__list">
              {totalsByCurrency.map((t) => (
                <li key={t.currency} className="cash-balances-totals__item">
                  {t.currency}: <CurrencyValue value={t.balance} currency={t.currency} />
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </>
    );
  };

  const renderLedgerBody = () => {
    if (dateRangeInvalid) {
      return (
        <WarningBanner
          severity="warning"
          message="Date from must be on or before date to."
          className="cash-page__banner"
        />
      );
    }
    if (ledgerLoading && !ledgerData) {
      return <LoadingState message="Loading ledger…" />;
    }
    if (ledgerError) {
      return <ErrorState title="Could not load ledger" message={ledgerError} />;
    }
    if (ledgerItems.length === 0) {
      return (
        <EmptyState
          title="No ledger entries"
          description="Deposits, withdrawals, and settlements appear here when recorded."
        />
      );
    }

    return (
      <>
        <div
          className={`cash-ledger-table-wrapper${ledgerLoading ? ' cash-ledger-table-wrapper--loading' : ''}`}
          aria-busy={ledgerLoading}
        >
          <table className="cash-ledger-table">
            <thead>
              <tr>
                <th>Date</th>
                {isAllScope ? <th>Portfolio</th> : null}
                <th>Type</th>
                <th>Currency</th>
                <th className="num-col">Amount</th>
                <th>Source</th>
                <th>Note</th>
                <th className="cash-ledger-table__actions-col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {ledgerItems.map((entry) => {
                const editable = isManualEditableCashEntry(entry);
                return (
                  <tr key={entry.id}>
                    <td>{entry.date}</td>
                    {isAllScope ? (
                      <td>
                        {entry.portfolio_name ||
                          (entry.portfolio_id != null ? `#${entry.portfolio_id}` : '—')}
                      </td>
                    ) : null}
                    <td>{cashEntryTypeLabel(entry.entry_type)}</td>
                    <td>{entry.currency}</td>
                    <td className="num-col">
                      <CurrencyValue
                        value={entry.amount}
                        currency={entry.currency}
                        tone={amountTone(entry.amount)}
                      />
                    </td>
                    <td>{entry.source_of_funds || '—'}</td>
                    <td>{entry.note || '—'}</td>
                    <td className="cash-ledger-table__actions-col">
                      {editable ? (
                        <div className="cash-ledger-actions">
                          <Button
                            variant="ghost"
                            className="cash-ledger-actions__btn"
                            aria-label={`Edit ${cashEntryTypeLabel(entry.entry_type)}`}
                            onClick={() => openEditModal(entry)}
                          >
                            <Edit2 size={16} aria-hidden />
                          </Button>
                          <Button
                            variant="ghost"
                            className="cash-ledger-actions__btn"
                            aria-label={`Delete ${cashEntryTypeLabel(entry.entry_type)}`}
                            onClick={() => handleDeleteEntry(entry)}
                          >
                            <Trash2 size={16} aria-hidden />
                          </Button>
                        </div>
                      ) : (
                        <span
                          className="cash-ledger-actions__protected"
                          title="System or linked entries cannot be edited here."
                        >
                          —
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {ledgerData && ledgerData.total > 0 ? (
          <div className="cash-ledger-pagination">
            <span>
              Page {ledgerData.page} of {ledgerPages} · {ledgerData.total} entries
            </span>
            <div className="cash-ledger-pagination__controls">
              <Button
                variant="secondary"
                disabled={ledgerPage <= 1 || ledgerLoading}
                onClick={() => setLedgerPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={ledgerPage >= ledgerPages || ledgerLoading}
                onClick={() => setLedgerPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </>
    );
  };

  return (
    <div className="cash-page">
      <PageHeader
        title="Cash"
        subtitle="Native cash balances by portfolio and currency. Amounts are stored in each currency — not converted for display on this page."
      />

      <CashAwarePortfolioStatus className="cash-page__cash-aware" />

      {statusMessage ? (
        <WarningBanner
          severity="success"
          message={statusMessage}
          className="cash-page__banner"
        />
      ) : null}

      {ledgerFutureImpact ? (
        <div className="cash-page__banner">
          <CashFutureImpactDisplay impact={ledgerFutureImpact} />
        </div>
      ) : null}

      {ledgerError && !ledgerFutureImpact ? (
        <WarningBanner
          severity="error"
          message={ledgerError}
          className="cash-page__banner"
        />
      ) : null}

      <div className="cash-page__actions">
        <Button
          variant="primary"
          onClick={() => {
            setEditingEntry(null);
            setDepositOpen(true);
          }}
        >
          Add Deposit
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            setEditingEntry(null);
            setWithdrawalOpen(true);
          }}
        >
          Add Withdrawal
        </Button>
        <Button
          variant="secondary"
          onClick={() => setBackfillOpen(true)}
        >
          Backfill Cash
        </Button>
      </div>

      <SectionCard
        title="Cash balances"
        subtitle={
          isAllScope
            ? 'All active portfolios'
            : selectedPortfolioName || 'Selected portfolio'
        }
      >
        {renderBalancesBody()}
      </SectionCard>

      <SectionCard title="Cash ledger" subtitle="Deposits, withdrawals, and settlements">
        <div className="cash-ledger-filters">
          <div className="form-group">
            <label htmlFor="cash-filter-currency">Currency</label>
            <select
              id="cash-filter-currency"
              value={filterCurrency}
              onChange={(e) => setFilterCurrency(e.target.value)}
            >
              <option value="">All currencies</option>
              {SUPPORTED_CASH_CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="cash-filter-type">Entry type</label>
            <select
              id="cash-filter-type"
              value={filterEntryType}
              onChange={(e) => setFilterEntryType(e.target.value)}
            >
              {LEDGER_ENTRY_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value || 'all'} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="cash-filter-from">From</label>
            <input
              id="cash-filter-from"
              type="date"
              value={filterDateFrom}
              onChange={(e) => setFilterDateFrom(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label htmlFor="cash-filter-to">To</label>
            <input
              id="cash-filter-to"
              type="date"
              value={filterDateTo}
              onChange={(e) => setFilterDateTo(e.target.value)}
            />
          </div>
        </div>
        {renderLedgerBody()}
      </SectionCard>

      <CashEntryModal
        mode="deposit"
        open={depositOpen}
        onClose={closeEntryModals}
        activePortfolios={activePortfolios}
        requirePortfolioPick={isAllScope}
        defaultPortfolioId={defaultPortfolioId}
        editingEntry={
          editingEntry?.entry_type === 'CASH_DEPOSIT' ? editingEntry : null
        }
        onSuccess={handleEntrySuccess}
      />
      <CashEntryModal
        mode="withdrawal"
        open={withdrawalOpen}
        onClose={closeEntryModals}
        activePortfolios={activePortfolios}
        requirePortfolioPick={isAllScope}
        defaultPortfolioId={defaultPortfolioId}
        editingEntry={
          editingEntry?.entry_type === 'CASH_WITHDRAWAL' ? editingEntry : null
        }
        onSuccess={handleEntrySuccess}
      />
      <CashBackfillWizard
        open={backfillOpen}
        onClose={() => setBackfillOpen(false)}
        activePortfolios={activePortfolios}
        requirePortfolioPick={isAllScope}
        defaultPortfolioId={defaultPortfolioId}
        onApplySuccess={refreshAll}
      />
    </div>
  );
}
