import { useCallback, useEffect, useState } from 'react';
import { createCashMovement, fetchCashMovements } from '../api';
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  WarningBanner,
} from './ui';

const MOVEMENT_TYPES = [
  { value: 'MANUAL_DEPOSIT', label: 'Manual deposit' },
  { value: 'MANUAL_WITHDRAWAL', label: 'Manual withdrawal' },
  { value: 'ADJUSTMENT', label: 'Adjustment' },
];

function formatMovementType(type) {
  if (!type) return '—';
  const labels = {
    FD_OPENING: 'FD opening',
    FD_INTEREST: 'FD interest',
    FD_MATURITY_PRINCIPAL: 'FD maturity principal',
    FD_MATURITY_INTEREST: 'FD maturity interest',
    FD_CLOSURE_PRINCIPAL: 'FD closure principal',
    FD_CLOSURE_INTEREST: 'FD closure interest',
    OPENING_BALANCE: 'Opening balance',
  };
  if (labels[type]) return labels[type];
  return type
    .split('_')
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(' ');
}

function formatTimestamp(iso) {
  if (!iso) return '—';
  return iso.replace('T', ' ').slice(0, 19);
}

function emptyForm() {
  return {
    movement_type: 'MANUAL_DEPOSIT',
    direction: 'CREDIT',
    amount: '',
    movement_date: new Date().toISOString().slice(0, 10),
    description: '',
  };
}

function directionForType(movementType) {
  if (movementType === 'MANUAL_DEPOSIT') return 'CREDIT';
  if (movementType === 'MANUAL_WITHDRAWAL') return 'DEBIT';
  return null;
}

export default function CashMovementManagement({ account, onAccountUpdated, refreshKey = 0 }) {
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadMovements = useCallback(async () => {
    if (!account?.id) return;
    setLoading(true);
    setError('');
    try {
      const data = await fetchCashMovements({ bank_account_id: account.id });
      setMovements(Array.isArray(data?.items) ? data.items : []);
    } catch (err) {
      setError(err.message || 'Failed to load cash movements.');
      setMovements([]);
    } finally {
      setLoading(false);
    }
  }, [account?.id]);

  useEffect(() => {
    loadMovements();
  }, [loadMovements, refreshKey]);

  const openModal = () => {
    setForm(emptyForm());
    setFormError('');
    setStatus('');
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setFormError('');
  };

  const handleTypeChange = (movementType) => {
    const fixedDirection = directionForType(movementType);
    setForm((prev) => ({
      ...prev,
      movement_type: movementType,
      direction: fixedDirection ?? prev.direction,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    const amount = parseFloat(form.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setFormError('Amount must be greater than zero.');
      return;
    }
    if (!form.movement_date) {
      setFormError('Movement date is required.');
      return;
    }

    const payload = {
      bank_account_id: account.id,
      movement_type: form.movement_type,
      amount: form.amount,
      movement_date: form.movement_date,
    };
    if (form.description.trim()) {
      payload.description = form.description.trim();
    }
    if (form.movement_type === 'ADJUSTMENT') {
      payload.direction = form.direction;
    }

    setSubmitting(true);
    try {
      await createCashMovement(payload);
      setModalOpen(false);
      setStatus('Cash movement recorded.');
      await loadMovements();
      if (onAccountUpdated) {
        await onAccountUpdated();
      }
    } catch (err) {
      setFormError(err.message || 'Failed to record cash movement.');
    } finally {
      setSubmitting(false);
    }
  };

  const fixedDirection = directionForType(form.movement_type);

  if (!account) {
    return null;
  }

  return (
    <div className="cash-movement-management">
      <div className="cash-movement-management__header">
        <div>
          <h3 className="cash-movement-management__title">{account.name}</h3>
          <p className="settings-hint cash-movement-management__meta">
            {account.institution_name} · {account.account_number} · {account.currency}
          </p>
          <p className="cash-movement-management__balance">
            Current balance: <strong>{account.current_balance}</strong> {account.currency}
          </p>
          <p className="settings-hint">
            Bank cash is ledger-tracked but not included in portfolio value yet.
          </p>
        </div>
        <Button type="button" variant="primary" onClick={openModal}>
          Record movement
        </Button>
      </div>

      {status ? (
        <WarningBanner severity="success" message={status} className="settings-banner" />
      ) : null}

      {loading ? <LoadingState message="Loading cash movements…" /> : null}

      {!loading && error ? (
        <ErrorState title="Could not load movements" message={error} onRetry={loadMovements} />
      ) : null}

      {!loading && !error && movements.length === 0 ? (
        <EmptyState
          title="No movements yet"
          description="No cash movements recorded for this bank account yet."
        />
      ) : null}

      {!loading && !error && movements.length > 0 ? (
        <div className="cash-movement-table-wrap">
          <table className="cash-movement-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Type</th>
                <th>Direction</th>
                <th className="num-col">Amount</th>
                <th>Description</th>
                <th>Source</th>
                <th>Created at</th>
              </tr>
            </thead>
            <tbody>
              {movements.map((m) => (
                <tr key={m.id}>
                  <td>{m.movement_date}</td>
                  <td>{formatMovementType(m.movement_type)}</td>
                  <td>{m.direction}</td>
                  <td className="num-col">{m.amount}</td>
                  <td>{m.description || '—'}</td>
                  <td>{m.source}</td>
                  <td>{formatTimestamp(m.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {modalOpen ? (
        <div
          className="cash-movement-modal-backdrop"
          role="presentation"
          onClick={closeModal}
        >
          <div
            className="cash-movement-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="cash-movement-modal-title"
            onClick={(ev) => ev.stopPropagation()}
          >
            <h2 id="cash-movement-modal-title">Record cash movement</h2>
            {formError ? <WarningBanner severity="error" message={formError} /> : null}
            <form onSubmit={handleSubmit} className="settings-form">
              <div className="form-group">
                <label htmlFor="cm-type">Movement type</label>
                <select
                  id="cm-type"
                  value={form.movement_type}
                  onChange={(e) => handleTypeChange(e.target.value)}
                  required
                >
                  {MOVEMENT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="cm-direction">Direction</label>
                {fixedDirection ? (
                  <p id="cm-direction" className="settings-hint">
                    {fixedDirection} (fixed for this movement type)
                  </p>
                ) : (
                  <select
                    id="cm-direction"
                    value={form.direction}
                    onChange={(e) => setForm((p) => ({ ...p, direction: e.target.value }))}
                    required
                  >
                    <option value="CREDIT">Credit</option>
                    <option value="DEBIT">Debit</option>
                  </select>
                )}
              </div>
              <div className="form-group">
                <label htmlFor="cm-amount">Amount</label>
                <input
                  id="cm-amount"
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={form.amount}
                  onChange={(e) => setForm((p) => ({ ...p, amount: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="cm-date">Movement date</label>
                <input
                  id="cm-date"
                  type="date"
                  value={form.movement_date}
                  onChange={(e) => setForm((p) => ({ ...p, movement_date: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="cm-description">Description (optional)</label>
                <textarea
                  id="cm-description"
                  value={form.description}
                  onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                  rows={2}
                />
              </div>
              <div className="cash-movement-modal__actions">
                <Button type="submit" variant="primary" disabled={submitting}>
                  {submitting ? 'Saving…' : 'Save movement'}
                </Button>
                <Button type="button" variant="secondary" onClick={closeModal}>
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
