import { useCallback, useEffect, useState } from 'react';
import { createCashMovement, fetchCashMovements, reverseCashMovement } from '../api';
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
    FD_OPENING_REVERSAL: 'FD opening reversal',
    FD_INTEREST: 'FD interest',
    FD_MATURITY_PRINCIPAL: 'FD maturity principal',
    FD_MATURITY_INTEREST: 'FD maturity interest',
    FD_CLOSURE_PRINCIPAL: 'FD closure principal',
    FD_CLOSURE_INTEREST: 'FD closure interest',
    OPENING_BALANCE: 'Opening balance',
    REVERSAL: 'Reversal',
    FD_INTEREST_REVERSAL: 'FD interest reversal',
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

const REVERSIBLE_MOVEMENT_TYPES = new Set([
  'MANUAL_DEPOSIT',
  'MANUAL_WITHDRAWAL',
  'ADJUSTMENT',
  'OPENING_BALANCE',
]);

function canReverseMovement(movement) {
  if (!movement || movement.is_reversal || movement.is_reversed) return false;
  if (movement.source !== 'MANUAL') return false;
  return REVERSIBLE_MOVEMENT_TYPES.has(movement.movement_type);
}

function emptyReverseForm() {
  return {
    reversal_date: new Date().toISOString().slice(0, 10),
    reason: '',
  };
}

function movementStatusLabel(movement) {
  if (movement.is_reversal) {
    const suffix = movement.reverses_id ? ` #${movement.reverses_id}` : '';
    return `Reversal (reverses${suffix})`;
  }
  if (movement.is_reversed) return 'Reversed';
  return '—';
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
  const [reverseModalOpen, setReverseModalOpen] = useState(false);
  const [reverseTarget, setReverseTarget] = useState(null);
  const [reverseForm, setReverseForm] = useState(emptyReverseForm);
  const [reverseError, setReverseError] = useState('');
  const [reverseSubmitting, setReverseSubmitting] = useState(false);

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

  const openReverseModal = (movement) => {
    setReverseTarget(movement);
    setReverseForm(emptyReverseForm());
    setReverseError('');
    setStatus('');
    setReverseModalOpen(true);
  };

  const closeReverseModal = () => {
    setReverseModalOpen(false);
    setReverseTarget(null);
    setReverseError('');
  };

  const handleReverseSubmit = async (e) => {
    e.preventDefault();
    setReverseError('');
    if (!reverseTarget?.id) return;
    if (!reverseForm.reason.trim()) {
      setReverseError('Reason is required for audit.');
      return;
    }
    if (!reverseForm.reversal_date) {
      setReverseError('Reversal date is required.');
      return;
    }
    setReverseSubmitting(true);
    try {
      await reverseCashMovement(reverseTarget.id, {
        reversal_date: reverseForm.reversal_date,
        reason: reverseForm.reason.trim(),
      });
      setReverseModalOpen(false);
      setReverseTarget(null);
      setStatus('Cash movement reversed. An opposite ledger entry was created.');
      await loadMovements();
      if (onAccountUpdated) {
        await onAccountUpdated();
      }
    } catch (err) {
      setReverseError(err.message || 'Failed to reverse cash movement.');
    } finally {
      setReverseSubmitting(false);
    }
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
                <th>Status</th>
                <th>Source</th>
                <th>Created at</th>
                <th>Actions</th>
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
                  <td>
                    {movementStatusLabel(m)}
                    {m.reversal_reason ? (
                      <span className="settings-hint"> — {m.reversal_reason}</span>
                    ) : null}
                  </td>
                  <td>{m.source}</td>
                  <td>{formatTimestamp(m.created_at)}</td>
                  <td>
                    {canReverseMovement(m) ? (
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => openReverseModal(m)}
                      >
                        Reverse
                      </Button>
                    ) : (
                      '—'
                    )}
                  </td>
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

      {reverseModalOpen && reverseTarget ? (
        <div
          className="cash-movement-modal-backdrop"
          role="presentation"
          onClick={closeReverseModal}
        >
          <div
            className="cash-movement-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="cash-movement-reverse-modal-title"
            onClick={(ev) => ev.stopPropagation()}
          >
            <h2 id="cash-movement-reverse-modal-title">Reverse cash movement</h2>
            <p className="settings-hint">
              This creates an opposite ledger entry. The original movement stays visible and is
              marked reversed.
            </p>
            {reverseError ? <WarningBanner severity="error" message={reverseError} /> : null}
            <form onSubmit={handleReverseSubmit} className="settings-form">
              <div className="form-group">
                <label htmlFor="cm-reverse-date">Reversal date</label>
                <input
                  id="cm-reverse-date"
                  type="date"
                  value={reverseForm.reversal_date}
                  onChange={(e) =>
                    setReverseForm((p) => ({ ...p, reversal_date: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="cm-reverse-reason">Reason (required)</label>
                <textarea
                  id="cm-reverse-reason"
                  value={reverseForm.reason}
                  onChange={(e) => setReverseForm((p) => ({ ...p, reason: e.target.value }))}
                  rows={3}
                  required
                />
              </div>
              <div className="cash-movement-modal__actions">
                <Button type="submit" variant="primary" disabled={reverseSubmitting}>
                  {reverseSubmitting ? 'Reversing…' : 'Confirm reversal'}
                </Button>
                <Button type="button" variant="secondary" onClick={closeReverseModal}>
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
