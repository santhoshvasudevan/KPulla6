import { useEffect, useMemo, useState } from 'react';
import {
  previewCashBackfill,
  applyCashBackfill,
  updatePortfolio,
  CashApiError,
} from '../api';
import { usePortfolio } from '../portfolioContext';
import { buildCashAwareEnablePayload } from '../utils/portfolioCashAware';
import { Button, WarningBanner, CurrencyValue } from './ui';
import './CashBackfillWizard.css';

const BACKFILL_INTRO =
  'This previews cash deposits needed before historical purchases. No data is changed until you apply.';

const BACKFILL_ENABLE_CONFIRM =
  'After enabling, new purchases in this portfolio require available same-currency cash. Existing transactions are not changed.';

function emptyConfigure(defaultPortfolioId = '') {
  return {
    portfolio_id: defaultPortfolioId,
    start_date: '',
    end_date: '',
  };
}

function formatCashAwareLabel(enabled) {
  return enabled ? 'On' : 'Off';
}

export default function CashBackfillWizard({
  open,
  onClose,
  activePortfolios,
  requirePortfolioPick,
  defaultPortfolioId,
  onApplySuccess,
}) {
  const { portfolios, reloadPortfolios } = usePortfolio();
  const [step, setStep] = useState('configure');
  const [form, setForm] = useState(() => emptyConfigure(defaultPortfolioId));
  const [preview, setPreview] = useState(null);
  const [applyResult, setApplyResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [enabling, setEnabling] = useState(false);
  const [enableSuccess, setEnableSuccess] = useState('');

  useEffect(() => {
    if (!open) return;
    setStep('configure');
    setForm(emptyConfigure(defaultPortfolioId));
    setPreview(null);
    setApplyResult(null);
    setLoading(false);
    setError('');
    setEnabling(false);
    setEnableSuccess('');
  }, [open, defaultPortfolioId]);

  const portfolioById = useMemo(() => {
    const map = new Map();
    for (const p of activePortfolios || []) {
      if (p?.id != null) map.set(p.id, p);
    }
    return map;
  }, [activePortfolios]);

  const selectedPortfolio = useMemo(() => {
    const id = Number(form.portfolio_id);
    if (!id || Number.isNaN(id)) return null;
    return portfolioById.get(id) ?? null;
  }, [form.portfolio_id, portfolioById]);

  const resultPortfolio = useMemo(() => {
    const id = applyResult?.portfolio_id;
    if (id == null) return null;
    return (portfolios || []).find((p) => p && p.id === id) ?? null;
  }, [applyResult, portfolios]);

  if (!open) return null;

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const buildRequestPayload = () => {
    const portfolioId = Number(form.portfolio_id);
    if (!portfolioId || Number.isNaN(portfolioId)) {
      throw new Error('Select a portfolio.');
    }
    if (form.start_date && form.end_date && form.start_date > form.end_date) {
      throw new Error('Start date must be on or before end date.');
    }
    return {
      portfolio_id: portfolioId,
      start_date: form.start_date || undefined,
      end_date: form.end_date || undefined,
      mode: 'shortfall',
    };
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
      const data = await previewCashBackfill(payload);
      if (data.row_errors?.length) {
        setError('Backfill preview has row errors. Resolve them before applying.');
      }
      setPreview(data);
      setStep('review');
    } catch (err) {
      setError(err.message || 'Could not load backfill preview.');
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
      const data = await applyCashBackfill(payload);
      setApplyResult(data);
      setStep('result');
      if (data.created_count > 0 && onApplySuccess) {
        await onApplySuccess();
      }
    } catch (err) {
      const blocking =
        err instanceof CashApiError
          ? err.blocking_warnings || err.data?.blocking_warnings
          : null;
      if (blocking?.length) {
        setError([err.message, ...blocking].filter(Boolean).join(' '));
      } else {
        setError(err.message || 'Could not apply backfill.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleEnableCashAware = async () => {
    const portfolio = resultPortfolio;
    if (!portfolio || portfolio.cash_aware_enabled) return;
    if (!window.confirm(BACKFILL_ENABLE_CONFIRM)) return;
    setError('');
    setEnableSuccess('');
    setEnabling(true);
    try {
      await updatePortfolio(portfolio.id, buildCashAwareEnablePayload(portfolio));
      await reloadPortfolios();
      setEnableSuccess('Cash-aware mode enabled for this portfolio.');
    } catch (err) {
      setError(err.message || 'Could not enable cash-aware mode.');
    } finally {
      setEnabling(false);
    }
  };

  const handleClose = () => {
    if (loading) return;
    onClose();
  };

  const proposedCount = preview?.summary?.proposed_deposit_count ?? 0;
  const proposedDeposits = preview?.proposed_deposits ?? [];
  const shortfalls = preview?.shortfalls ?? [];
  const totalsProposed = preview?.summary?.total_proposed_by_currency ?? [];
  const createdDeposits = applyResult?.created_deposits ?? [];
  const totalsCreated = applyResult?.summary?.total_created_by_currency ?? [];

  return (
    <div className="modal-overlay" role="presentation" onClick={handleClose}>
      <div
        className="modal-content cash-backfill-wizard"
        role="dialog"
        aria-labelledby="cash-backfill-wizard-title"
        onClick={(ev) => ev.stopPropagation()}
      >
        <h3 id="cash-backfill-wizard-title">Backfill cash</h3>

        {error ? (
          <WarningBanner severity="error" message={error} className="cash-backfill-wizard__banner" />
        ) : null}
        {enableSuccess ? (
          <WarningBanner
            severity="success"
            message={enableSuccess}
            className="cash-backfill-wizard__banner"
          />
        ) : null}

        {step === 'configure' ? (
          <form onSubmit={handlePreview}>
            <p className="cash-backfill-wizard__intro">{BACKFILL_INTRO}</p>

            {requirePortfolioPick || activePortfolios.length > 1 ? (
              <div className="form-group">
                <label htmlFor="backfill-portfolio">Portfolio</label>
                <select
                  id="backfill-portfolio"
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
              <label htmlFor="backfill-start">Start date (optional)</label>
              <input
                id="backfill-start"
                type="date"
                value={form.start_date}
                onChange={(e) => updateField('start_date', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="backfill-end">End date (optional)</label>
              <input
                id="backfill-end"
                type="date"
                value={form.end_date}
                onChange={(e) => updateField('end_date', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="backfill-mode">Mode</label>
              <input id="backfill-mode" type="text" value="shortfall" readOnly disabled />
            </div>

            <div className="cash-backfill-wizard__actions">
              <Button type="button" variant="ghost" onClick={handleClose} disabled={loading}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={loading}>
                {loading ? 'Loading preview…' : 'Preview backfill'}
              </Button>
            </div>
          </form>
        ) : null}

        {step === 'review' && preview ? (
          <div className="cash-backfill-wizard__review">
            <dl className="cash-backfill-wizard__meta">
              <div>
                <dt>Portfolio</dt>
                <dd>{preview.portfolio_name}</dd>
              </div>
              <div>
                <dt>Cash-aware mode</dt>
                <dd>{formatCashAwareLabel(preview.cash_aware_enabled)}</dd>
              </div>
              <div>
                <dt>Transactions in simulation</dt>
                <dd>{preview.summary?.transaction_count ?? '—'}</dd>
              </div>
              <div>
                <dt>Existing cash entries</dt>
                <dd>{preview.summary?.existing_cash_entry_count ?? '—'}</dd>
              </div>
              <div>
                <dt>Proposed deposits</dt>
                <dd>{proposedCount}</dd>
              </div>
            </dl>

            {preview.warnings?.length ? (
              <div className="cash-backfill-wizard__warnings">
                {preview.warnings.map((w) => (
                  <WarningBanner key={w} severity="warning" message={w} />
                ))}
              </div>
            ) : null}

            {preview.row_errors?.length ? (
              <div className="cash-backfill-wizard__warnings">
                {preview.row_errors.map((rowErr, idx) => (
                  <WarningBanner
                    key={`row-${idx}`}
                    severity="error"
                    message={
                      rowErr.message ||
                      `Row ${rowErr.row ?? idx + 1}: ${JSON.stringify(rowErr)}`
                    }
                  />
                ))}
              </div>
            ) : null}

            {totalsProposed.length > 0 ? (
              <div className="cash-backfill-wizard__totals">
                <p className="cash-backfill-wizard__totals-title">Total proposed by currency</p>
                <ul>
                  {totalsProposed.map((t) => (
                    <li key={t.currency}>
                      {t.currency}:{' '}
                      <CurrencyValue value={t.amount} currency={t.currency} />
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {proposedCount === 0 ? (
              <WarningBanner
                severity="success"
                message="No backfill deposits are needed for this range."
                className="cash-backfill-wizard__banner"
              />
            ) : (
              <>
                <h4 className="cash-backfill-wizard__table-title">Proposed deposits</h4>
                <div className="cash-backfill-wizard__table-wrap">
                  <table className="cash-backfill-wizard__table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Currency</th>
                        <th className="num-col">Amount</th>
                        <th>Source</th>
                        <th>Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {proposedDeposits.map((dep, idx) => (
                        <tr key={`${dep.date}-${dep.currency}-${idx}`}>
                          <td>{dep.date}</td>
                          <td>{dep.currency}</td>
                          <td className="num-col">
                            <CurrencyValue value={dep.amount} currency={dep.currency} />
                          </td>
                          <td>{dep.source_of_funds || '—'}</td>
                          <td>{dep.note || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {shortfalls.length > 0 ? (
              <>
                <h4 className="cash-backfill-wizard__table-title">Shortfalls</h4>
                <div className="cash-backfill-wizard__table-wrap">
                  <table className="cash-backfill-wizard__table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Currency</th>
                        <th className="num-col">Required</th>
                        <th className="num-col">Available before</th>
                        <th className="num-col">Shortfall</th>
                        <th>Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shortfalls.map((s, idx) => (
                        <tr key={`${s.date}-${s.currency}-${idx}`}>
                          <td>{s.date}</td>
                          <td>{s.currency}</td>
                          <td className="num-col">
                            <CurrencyValue value={s.required} currency={s.currency} />
                          </td>
                          <td className="num-col">
                            <CurrencyValue value={s.available_before} currency={s.currency} />
                          </td>
                          <td className="num-col">
                            <CurrencyValue
                              value={s.shortfall}
                              currency={s.currency}
                              tone="loss"
                            />
                          </td>
                          <td>{s.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}

            <div className="cash-backfill-wizard__actions">
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
                disabled={loading || proposedCount === 0 || preview.row_errors?.length > 0}
                onClick={handleApply}
              >
                {loading ? 'Applying…' : 'Apply backfill deposits'}
              </Button>
            </div>
          </div>
        ) : null}

        {step === 'result' && applyResult ? (
          <div className="cash-backfill-wizard__result">
            <dl className="cash-backfill-wizard__meta">
              <div>
                <dt>Created</dt>
                <dd>{applyResult.created_count}</dd>
              </div>
              <div>
                <dt>Skipped (already existed)</dt>
                <dd>{applyResult.skipped_existing_count}</dd>
              </div>
            </dl>

            {applyResult.cash_aware_enablement?.message ? (
              <WarningBanner
                severity="info"
                message={applyResult.cash_aware_enablement.message}
                className="cash-backfill-wizard__banner"
              />
            ) : null}

            {totalsCreated.length > 0 ? (
              <div className="cash-backfill-wizard__totals">
                <p className="cash-backfill-wizard__totals-title">Total created by currency</p>
                <ul>
                  {totalsCreated.map((t) => (
                    <li key={t.currency}>
                      {t.currency}:{' '}
                      <CurrencyValue value={t.amount} currency={t.currency} />
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {createdDeposits.length > 0 ? (
              <>
                <h4 className="cash-backfill-wizard__table-title">Created deposits</h4>
                <div className="cash-backfill-wizard__table-wrap">
                  <table className="cash-backfill-wizard__table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Currency</th>
                        <th className="num-col">Amount</th>
                        <th>Source</th>
                        <th>Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {createdDeposits.map((dep) => (
                        <tr key={dep.id}>
                          <td>{dep.date}</td>
                          <td>{dep.currency}</td>
                          <td className="num-col">
                            <CurrencyValue value={dep.amount} currency={dep.currency} />
                          </td>
                          <td>{dep.source_of_funds || '—'}</td>
                          <td>{dep.note || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}

            {applyResult.cash_aware_enabled === false && resultPortfolio ? (
              <div className="cash-backfill-wizard__enable">
                <Button
                  type="button"
                  variant="primary"
                  disabled={enabling || resultPortfolio.cash_aware_enabled}
                  onClick={handleEnableCashAware}
                >
                  {enabling ? 'Enabling…' : 'Enable cash-aware mode for this portfolio'}
                </Button>
                <p className="cash-backfill-wizard__enable-hint">
                  {BACKFILL_ENABLE_CONFIRM}
                </p>
              </div>
            ) : null}

            <div className="cash-backfill-wizard__actions">
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
