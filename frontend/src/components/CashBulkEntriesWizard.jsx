import { useEffect, useMemo, useState } from 'react';
import {
  previewCashBulkEntries,
  applyCashBulkEntries,
  CashApiError,
} from '../api';
import { SUPPORTED_CASH_CURRENCIES } from '../constants/cashCurrencies';
import { cashEntryTypeLabel } from '../utils/cashDisplay';
import { Button, WarningBanner, CurrencyValue } from './ui';
import './CashBulkEntriesWizard.css';

const INTRO =
  'Create multiple manual cash deposits or withdrawals from a schedule. Amounts and dates come from the server preview — nothing is written until you apply.';

const FREQUENCY_OPTIONS = [
  { value: 'once', label: 'Once' },
  { value: 'monthly', label: 'Monthly' },
];

function emptyForm(defaultPortfolioId = '') {
  return {
    portfolio_id: defaultPortfolioId,
    entry_type: 'CASH_DEPOSIT',
    currency: 'EUR',
    amount: '',
    start_date: '',
    end_date: '',
    frequency: 'monthly',
    source_of_funds: '',
    note: '',
  };
}

export default function CashBulkEntriesWizard({
  open,
  onClose,
  activePortfolios,
  requirePortfolioPick,
  defaultPortfolioId,
  onApplySuccess,
}) {
  const [step, setStep] = useState('configure');
  const [form, setForm] = useState(() => emptyForm(defaultPortfolioId));
  const [preview, setPreview] = useState(null);
  const [applyResult, setApplyResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setStep('configure');
    setForm(emptyForm(defaultPortfolioId));
    setPreview(null);
    setApplyResult(null);
    setLoading(false);
    setError('');
  }, [open, defaultPortfolioId]);

  const portfolioById = useMemo(() => {
    const map = new Map();
    for (const p of activePortfolios || []) {
      if (p?.id != null) map.set(p.id, p);
    }
    return map;
  }, [activePortfolios]);

  if (!open) return null;

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const buildRequestPayload = () => {
    const portfolioId = Number(form.portfolio_id);
    if (!portfolioId || Number.isNaN(portfolioId)) {
      throw new Error('Select a portfolio.');
    }
    const amount = parseFloat(form.amount);
    if (!form.amount || Number.isNaN(amount) || amount <= 0) {
      throw new Error('Enter an amount greater than zero.');
    }
    if (!form.start_date) {
      throw new Error('Start date is required.');
    }
    if (form.frequency === 'monthly') {
      if (!form.end_date) {
        throw new Error('End date is required for monthly frequency.');
      }
      if (form.start_date > form.end_date) {
        throw new Error('Start date must be on or before end date.');
      }
    }
    const payload = {
      portfolio_id: portfolioId,
      entry_type: form.entry_type,
      currency: form.currency,
      amount,
      start_date: form.start_date,
      frequency: form.frequency,
      source_of_funds: form.source_of_funds || '',
      note: form.note || '',
    };
    if (form.frequency === 'monthly' || form.end_date) {
      payload.end_date = form.end_date || form.start_date;
    }
    return payload;
  };

  const handlePreview = async (e) => {
    e.preventDefault();
    setError('');
    setPreview(null);
    setApplyResult(null);
    let payload;
    try {
      payload = buildRequestPayload();
    } catch (err) {
      setError(err.message);
      return;
    }
    setLoading(true);
    try {
      const data = await previewCashBulkEntries(payload);
      setPreview(data);
      setStep('review');
    } catch (err) {
      setError(err.message || 'Could not load preview.');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (loading) return;
    setError('');
    let payload;
    try {
      payload = buildRequestPayload();
    } catch (err) {
      setError(err.message);
      return;
    }
    setLoading(true);
    try {
      const data = await applyCashBulkEntries(payload);
      setApplyResult(data);
      setStep('result');
      if (data.created_count > 0 && onApplySuccess) {
        await onApplySuccess();
      }
    } catch (err) {
      if (err instanceof CashApiError && err.data?.warnings?.length) {
        setError([err.message, ...err.data.warnings].filter(Boolean).join(' '));
      } else {
        setError(err.message || 'Could not apply bulk entries.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (loading) return;
    onClose();
  };

  const entries = preview?.entries ?? [];
  const warnings = preview?.warnings ?? [];
  const createdEntries = applyResult?.created_entries ?? [];

  return (
    <div className="modal-overlay" role="presentation" onClick={handleClose}>
      <div
        className="modal-content cash-bulk-wizard"
        role="dialog"
        aria-labelledby="cash-bulk-wizard-title"
        onClick={(ev) => ev.stopPropagation()}
      >
        <h3 id="cash-bulk-wizard-title">Add bulk cash entries</h3>

        {error ? (
          <WarningBanner severity="error" message={error} className="cash-bulk-wizard__banner" />
        ) : null}

        {step === 'configure' ? (
          <form onSubmit={handlePreview}>
            <p className="cash-bulk-wizard__intro">{INTRO}</p>

            {requirePortfolioPick || activePortfolios.length > 1 ? (
              <div className="form-group">
                <label htmlFor="bulk-portfolio">Portfolio</label>
                <select
                  id="bulk-portfolio"
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
            ) : activePortfolios.length === 1 ? (
              <div className="form-group">
                <label>Portfolio</label>
                <p>{activePortfolios[0].name}</p>
              </div>
            ) : null}

            <div className="form-group">
              <label htmlFor="bulk-entry-type">Entry type</label>
              <select
                id="bulk-entry-type"
                value={form.entry_type}
                onChange={(e) => updateField('entry_type', e.target.value)}
              >
                <option value="CASH_DEPOSIT">Deposit</option>
                <option value="CASH_WITHDRAWAL">Withdrawal</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="bulk-currency">Currency</label>
              <select
                id="bulk-currency"
                value={form.currency}
                onChange={(e) => updateField('currency', e.target.value)}
              >
                {SUPPORTED_CASH_CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="bulk-amount">Amount (per entry)</label>
              <input
                id="bulk-amount"
                type="number"
                min="0"
                step="0.01"
                value={form.amount}
                onChange={(e) => updateField('amount', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="bulk-start">Start date</label>
              <input
                id="bulk-start"
                type="date"
                value={form.start_date}
                onChange={(e) => updateField('start_date', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="bulk-end">
                End date{form.frequency === 'once' ? ' (optional)' : ''}
              </label>
              <input
                id="bulk-end"
                type="date"
                value={form.end_date}
                onChange={(e) => updateField('end_date', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="bulk-frequency">Frequency</label>
              <select
                id="bulk-frequency"
                value={form.frequency}
                onChange={(e) => updateField('frequency', e.target.value)}
              >
                {FREQUENCY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="bulk-source">Source of funds</label>
              <input
                id="bulk-source"
                type="text"
                value={form.source_of_funds}
                onChange={(e) => updateField('source_of_funds', e.target.value)}
                placeholder="Optional"
              />
            </div>

            <div className="form-group">
              <label htmlFor="bulk-note">Note</label>
              <textarea
                id="bulk-note"
                rows={2}
                value={form.note}
                onChange={(e) => updateField('note', e.target.value)}
                placeholder="Optional"
              />
            </div>

            <div className="cash-bulk-wizard__actions">
              <Button type="button" variant="ghost" onClick={handleClose} disabled={loading}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={loading}>
                {loading ? 'Loading preview…' : 'Preview schedule'}
              </Button>
            </div>
          </form>
        ) : null}

        {step === 'review' && preview ? (
          <div className="cash-bulk-wizard__review">
            <dl className="cash-bulk-wizard__meta">
              <div>
                <dt>Portfolio</dt>
                <dd>{preview.portfolio_name}</dd>
              </div>
              <div>
                <dt>Entries</dt>
                <dd>{preview.entry_count}</dd>
              </div>
              {preview.duplicate_count > 0 ? (
                <div>
                  <dt>Duplicates</dt>
                  <dd>{preview.duplicate_count}</dd>
                </div>
              ) : null}
            </dl>

            {warnings.length > 0 ? (
              <div className="cash-bulk-wizard__warnings">
                {warnings.map((w) => (
                  <WarningBanner key={w} severity="warning" message={w} />
                ))}
              </div>
            ) : null}

            {preview.total_by_currency?.length > 0 ? (
              <div className="cash-bulk-wizard__totals">
                <p className="cash-bulk-wizard__totals-title">Total by currency</p>
                <ul>
                  {preview.total_by_currency.map((t) => (
                    <li key={t.currency}>
                      {t.currency}:{' '}
                      <CurrencyValue value={t.amount} currency={t.currency} />
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {entries.length > 0 ? (
              <>
                <h4 className="cash-bulk-wizard__table-title">Scheduled entries</h4>
                <div className="cash-bulk-wizard__table-wrap">
                  <table className="cash-bulk-wizard__table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Currency</th>
                        <th className="num-col">Amount</th>
                        <th>Source</th>
                        <th>Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entries.map((row, idx) => (
                        <tr key={`${row.date}-${row.currency}-${idx}`}>
                          <td>{row.date}</td>
                          <td>{cashEntryTypeLabel(row.entry_type)}</td>
                          <td>{row.currency}</td>
                          <td className="num-col">
                            <CurrencyValue value={row.amount} currency={row.currency} />
                          </td>
                          <td>{row.source_of_funds || '—'}</td>
                          <td>{row.note || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <WarningBanner
                severity="info"
                message="No entries in this schedule."
                className="cash-bulk-wizard__banner"
              />
            )}

            <div className="cash-bulk-wizard__actions">
              <Button type="button" variant="ghost" onClick={handleClose} disabled={loading}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setStep('configure');
                  setError('');
                }}
                disabled={loading}
              >
                Back
              </Button>
              <Button
                type="button"
                variant="primary"
                disabled={loading || entries.length === 0}
                onClick={handleApply}
              >
                {loading ? 'Applying…' : 'Apply bulk entries'}
              </Button>
            </div>
          </div>
        ) : null}

        {step === 'result' && applyResult ? (
          <div className="cash-bulk-wizard__result">
            <dl className="cash-bulk-wizard__meta">
              <div>
                <dt>Created</dt>
                <dd>{applyResult.created_count}</dd>
              </div>
              <div>
                <dt>Skipped (already existed)</dt>
                <dd>{applyResult.skipped_existing_count}</dd>
              </div>
            </dl>

            {applyResult.total_by_currency?.length > 0 ? (
              <div className="cash-bulk-wizard__totals">
                <p className="cash-bulk-wizard__totals-title">Total created by currency</p>
                <ul>
                  {applyResult.total_by_currency.map((t) => (
                    <li key={t.currency}>
                      {t.currency}:{' '}
                      <CurrencyValue value={t.amount} currency={t.currency} />
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {createdEntries.length > 0 ? (
              <>
                <h4 className="cash-bulk-wizard__table-title">Created entries</h4>
                <div className="cash-bulk-wizard__table-wrap">
                  <table className="cash-bulk-wizard__table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Currency</th>
                        <th className="num-col">Amount</th>
                        <th>Source</th>
                        <th>Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {createdEntries.map((row) => (
                        <tr key={row.id}>
                          <td>{row.date}</td>
                          <td>{cashEntryTypeLabel(row.entry_type)}</td>
                          <td>{row.currency}</td>
                          <td className="num-col">
                            <CurrencyValue value={row.amount} currency={row.currency} />
                          </td>
                          <td>{row.source_of_funds || '—'}</td>
                          <td>{row.note || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}

            <div className="cash-bulk-wizard__actions">
              <Button type="button" variant="primary" onClick={handleClose} disabled={loading}>
                Done
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
