import { useState } from 'react';
import { createPortfolio, updatePortfolio, deletePortfolio } from '../api';
import { usePortfolio } from '../portfolioContext';
import {
  buildCashAwareEnablePayload,
  CASH_AWARE_ENABLE_CONFIRM,
  CASH_AWARE_OFF_MESSAGE,
  CASH_AWARE_ON_MESSAGE,
} from '../utils/portfolioCashAware';
import { Button, WarningBanner } from './ui';

const CURRENCIES = ['EUR', 'USD', 'INR', 'GBP', 'CHF'];
const MAX_ACTIVE_PORTFOLIOS = 5;

function emptyCreateForm() {
  return { name: '', description: '', base_currency: 'EUR' };
}

export default function PortfolioManagement() {
  const { portfolios, reloadPortfolios, selectPortfolio } = usePortfolio();
  const activePortfolios = (portfolios || []).filter((p) => p && p.is_active);

  const [createForm, setCreateForm] = useState(emptyCreateForm);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState('');

  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ name: '', description: '', base_currency: 'EUR' });
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState('');

  const [status, setStatus] = useState('');
  const [deactivatingId, setDeactivatingId] = useState(null);
  const [enablingCashAwareId, setEnablingCashAwareId] = useState(null);

  const atMax = activePortfolios.length >= MAX_ACTIVE_PORTFOLIOS;

  const handleCreateChange = (e) => {
    const { name, value } = e.target;
    setCreateForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    setCreateError('');
    setStatus('');
    const name = createForm.name.trim();
    if (!name) {
      setCreateError('Portfolio name is required.');
      return;
    }
    setCreateSubmitting(true);
    try {
      const payload = {
        name,
        base_currency: createForm.base_currency || 'EUR',
      };
      const desc = createForm.description.trim();
      if (desc) payload.description = desc;
      const created = await createPortfolio(payload);
      await reloadPortfolios();
      if (created?.id != null) {
        await selectPortfolio(created.id, created.name || name, { portfolio: created });
      }
      setCreateForm(emptyCreateForm());
      setStatus(`Portfolio "${created?.name || name}" created.`);
    } catch (err) {
      setCreateError(err.message || 'Failed to create portfolio.');
    } finally {
      setCreateSubmitting(false);
    }
  };

  const startEdit = (portfolio) => {
    setEditingId(portfolio.id);
    setEditForm({
      name: portfolio.name || '',
      description: portfolio.description || '',
      base_currency: portfolio.base_currency || 'EUR',
    });
    setEditError('');
    setStatus('');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditError('');
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (editingId == null) return;
    setEditError('');
    setStatus('');
    const name = editForm.name.trim();
    if (!name) {
      setEditError('Portfolio name is required.');
      return;
    }
    setEditSubmitting(true);
    try {
      const payload = {
        name,
        base_currency: editForm.base_currency || 'EUR',
        description: editForm.description.trim() || null,
        is_active: true,
      };
      await updatePortfolio(editingId, payload);
      await reloadPortfolios();
      setEditingId(null);
      setStatus(`Portfolio "${name}" updated.`);
    } catch (err) {
      setEditError(err.message || 'Failed to update portfolio.');
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleEnableCashAware = async (portfolio) => {
    if (!window.confirm(CASH_AWARE_ENABLE_CONFIRM)) return;
    setStatus('');
    setCreateError('');
    setEditError('');
    setEnablingCashAwareId(portfolio.id);
    try {
      await updatePortfolio(portfolio.id, buildCashAwareEnablePayload(portfolio));
      await reloadPortfolios();
      setStatus(`Cash-aware mode enabled for "${portfolio.name}".`);
    } catch (err) {
      setCreateError(err.message || 'Failed to enable cash-aware mode.');
    } finally {
      setEnablingCashAwareId(null);
    }
  };

  const handleDeactivate = async (portfolio) => {
    if (portfolio.is_default) return;
    if (!window.confirm(`Deactivate portfolio "${portfolio.name}"? Transactions are kept.`)) return;
    setStatus('');
    setCreateError('');
    setEditError('');
    setDeactivatingId(portfolio.id);
    try {
      await deletePortfolio(portfolio.id);
      await reloadPortfolios();
      setStatus(`Portfolio "${portfolio.name}" deactivated.`);
    } catch (err) {
      setCreateError(err.message || 'Failed to deactivate portfolio.');
    } finally {
      setDeactivatingId(null);
    }
  };

  return (
    <div className="portfolio-management">
      <p className="settings-hint portfolio-management__intro">
        Manage real portfolios (max {MAX_ACTIVE_PORTFOLIOS} active, including Default). All Portfolios
        is a virtual view only and cannot receive transactions directly.
      </p>

      {status ? (
        <WarningBanner severity="success" message={status} className="settings-banner" />
      ) : null}
      {createError ? (
        <WarningBanner severity="error" message={createError} className="settings-banner" />
      ) : null}

      <form className="portfolio-management__create" onSubmit={handleCreateSubmit}>
        <h3 className="portfolio-management__subheading">Create portfolio</h3>
        <div className="portfolio-management__create-grid">
          <div className="form-group">
            <label htmlFor="portfolio-create-name">Name</label>
            <input
              id="portfolio-create-name"
              name="name"
              type="text"
              value={createForm.name}
              onChange={handleCreateChange}
              required
              disabled={atMax || createSubmitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="portfolio-create-currency">Base currency</label>
            <select
              id="portfolio-create-currency"
              name="base_currency"
              value={createForm.base_currency}
              onChange={handleCreateChange}
              disabled={atMax || createSubmitting}
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group portfolio-management__description">
            <label htmlFor="portfolio-create-description">Description (optional)</label>
            <input
              id="portfolio-create-description"
              name="description"
              type="text"
              value={createForm.description}
              onChange={handleCreateChange}
              disabled={atMax || createSubmitting}
            />
          </div>
        </div>
        {atMax ? (
          <p className="settings-hint">Maximum of {MAX_ACTIVE_PORTFOLIOS} active portfolios reached.</p>
        ) : null}
        <Button type="submit" variant="primary" disabled={atMax || createSubmitting}>
          {createSubmitting ? 'Creating…' : 'Create portfolio'}
        </Button>
      </form>

      <div className="portfolio-management__table-wrap">
        <table className="portfolio-management__table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Base currency</th>
              <th>Default</th>
              <th>Cash-aware</th>
              <th className="portfolio-management__actions-col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {activePortfolios.length === 0 ? (
              <tr>
                <td colSpan={5}>No active portfolios.</td>
              </tr>
            ) : (
              activePortfolios.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{p.base_currency || 'EUR'}</td>
                  <td>{p.is_default ? 'Yes' : '—'}</td>
                  <td>
                    <span
                      className="portfolio-management__cash-aware-label"
                      title={
                        p.cash_aware_enabled ? CASH_AWARE_ON_MESSAGE : CASH_AWARE_OFF_MESSAGE
                      }
                    >
                      {p.cash_aware_enabled ? 'On' : 'Off'}
                    </span>
                  </td>
                  <td className="portfolio-management__actions-col">
                    <div className="portfolio-management__actions">
                      {!p.cash_aware_enabled ? (
                        <Button
                          variant="secondary"
                          type="button"
                          disabled={enablingCashAwareId === p.id}
                          onClick={() => handleEnableCashAware(p)}
                        >
                          {enablingCashAwareId === p.id ? 'Enabling…' : 'Enable cash-aware'}
                        </Button>
                      ) : null}
                      <Button variant="ghost" type="button" onClick={() => startEdit(p)}>
                        Edit
                      </Button>
                      {p.is_default ? (
                        <span className="portfolio-management__default-note" title="Default portfolio cannot be deactivated">
                          —
                        </span>
                      ) : (
                        <Button
                          variant="danger"
                          type="button"
                          disabled={deactivatingId === p.id}
                          onClick={() => handleDeactivate(p)}
                        >
                          {deactivatingId === p.id ? 'Deactivating…' : 'Deactivate'}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {editingId != null ? (
        <div className="portfolio-management__edit-overlay" role="dialog" aria-modal="true" aria-labelledby="portfolio-edit-title">
          <div className="portfolio-management__edit-panel">
            <h3 id="portfolio-edit-title">Edit portfolio</h3>
            {editError ? <WarningBanner severity="error" message={editError} /> : null}
            <form className="portfolio-management__edit-form" onSubmit={handleEditSubmit}>
              <div className="form-group">
                <label htmlFor="portfolio-edit-name">Name</label>
                <input
                  id="portfolio-edit-name"
                  name="name"
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, name: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="portfolio-edit-currency">Base currency</label>
                <select
                  id="portfolio-edit-currency"
                  name="base_currency"
                  value={editForm.base_currency}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, base_currency: e.target.value }))}
                >
                  {CURRENCIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="portfolio-edit-description">Description (optional)</label>
                <input
                  id="portfolio-edit-description"
                  name="description"
                  type="text"
                  value={editForm.description}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, description: e.target.value }))}
                />
              </div>
              <div className="portfolio-management__edit-actions">
                <Button type="button" variant="secondary" onClick={cancelEdit} disabled={editSubmitting}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={editSubmitting}>
                  {editSubmitting ? 'Saving…' : 'Save changes'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
