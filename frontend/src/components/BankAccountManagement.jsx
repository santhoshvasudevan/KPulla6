import { useEffect, useState } from 'react';
import {
  createBankAccount,
  deleteBankAccount,
  fetchBankAccounts,
  fetchPortfolios,
  seedBankAccountOpeningBalance,
  updateBankAccount,
} from '../api';
import CashMovementManagement from './CashMovementManagement';
import { Button, WarningBanner } from './ui';

const CURRENCIES = ['EUR', 'USD', 'INR', 'GBP', 'CHF'];

const PORTFOLIO_LINK_HELP =
  'Linking controls where this bank cash appears in portfolio views. It does not create a cash movement or change the bank balance.';

function emptyForm() {
  return {
    name: '',
    institution_name: '',
    account_number: '',
    currency: 'INR',
    opening_balance: '0',
    current_balance: '0',
    portfolio_id: '',
    comment: '',
  };
}

function linkedPortfolioLabel(account) {
  if (account?.portfolio_id && account?.portfolio_name) {
    return account.portfolio_name;
  }
  if (account?.portfolio_assignment_status === 'AMBIGUOUS') {
    return 'Ambiguous link';
  }
  return 'Unlinked';
}

export default function BankAccountManagement() {
  const [accounts, setAccounts] = useState([]);
  const [portfolios, setPortfolios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [createForm, setCreateForm] = useState(emptyForm());
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(emptyForm());
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [linkModalAccount, setLinkModalAccount] = useState(null);
  const [linkModalPortfolioId, setLinkModalPortfolioId] = useState('');
  const [linkModalError, setLinkModalError] = useState('');
  const [linkModalSubmitting, setLinkModalSubmitting] = useState(false);
  const [linkSubmittingId, setLinkSubmittingId] = useState(null);
  const [deactivatingId, setDeactivatingId] = useState(null);
  const [seedingId, setSeedingId] = useState(null);
  const [selectedAccountId, setSelectedAccountId] = useState(null);
  const [movementsRefreshKey, setMovementsRefreshKey] = useState(0);

  const reload = async () => {
    setLoading(true);
    setError('');
    try {
      const [accountData, portfolioData] = await Promise.all([
        fetchBankAccounts(),
        fetchPortfolios(),
      ]);
      setAccounts(Array.isArray(accountData) ? accountData : []);
      setPortfolios((portfolioData || []).filter((p) => p.is_active));
    } catch (err) {
      setError(err.message || 'Failed to load bank accounts.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  const portfolioPayload = (portfolioId) => {
    if (!portfolioId) return { portfolio_id: null };
    return { portfolio_id: Number(portfolioId) };
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setStatus('');
    setError('');
    setCreateSubmitting(true);
    try {
      const payload = {
        name: createForm.name.trim(),
        institution_name: createForm.institution_name.trim(),
        account_number: createForm.account_number.trim(),
        currency: createForm.currency,
        opening_balance: createForm.opening_balance,
        current_balance: createForm.current_balance,
        include_in_portfolio_value: false,
        comment: createForm.comment.trim(),
      };
      if (createForm.portfolio_id) {
        payload.portfolio_id = Number(createForm.portfolio_id);
      }
      await createBankAccount(payload);
      setCreateForm(emptyForm());
      setStatus('Bank account created.');
      await reload();
    } catch (err) {
      setError(err.message || 'Failed to create bank account.');
    } finally {
      setCreateSubmitting(false);
    }
  };

  const startEdit = (account) => {
    setEditingId(account.id);
    setEditForm({
      name: account.name || '',
      institution_name: account.institution_name || '',
      account_number: account.account_number || '',
      currency: account.currency || 'INR',
      opening_balance: String(account.opening_balance ?? 0),
      current_balance: String(account.current_balance ?? 0),
      include_in_portfolio_value: Boolean(account.include_in_portfolio_value),
      portfolio_id: account.portfolio_id ? String(account.portfolio_id) : '',
      comment: account.comment || '',
    });
    setStatus('');
    setError('');
  };

  const handleEdit = async (e) => {
    e.preventDefault();
    if (editingId == null) return;
    const editingAccount = accounts.find((a) => a.id === editingId);
    const ledgerActive = editingAccount?.has_ledger_entries;
    setEditSubmitting(true);
    setError('');
    try {
      const payload = {
        name: editForm.name.trim(),
        institution_name: editForm.institution_name.trim(),
        account_number: editForm.account_number.trim(),
        currency: editForm.currency,
        opening_balance: editForm.opening_balance,
        include_in_portfolio_value: editForm.include_in_portfolio_value,
        comment: editForm.comment.trim(),
        ...portfolioPayload(editForm.portfolio_id),
      };
      if (!ledgerActive) {
        payload.current_balance = editForm.current_balance;
      }
      await updateBankAccount(editingId, payload);
      setEditingId(null);
      setStatus('Bank account updated.');
      await reload();
    } catch (err) {
      setError(err.message || 'Failed to update bank account.');
    } finally {
      setEditSubmitting(false);
    }
  };

  const openLinkModal = (account) => {
    setLinkModalAccount(account);
    setLinkModalPortfolioId(account.portfolio_id ? String(account.portfolio_id) : '');
    setLinkModalError('');
    setStatus('');
    setError('');
  };

  const closeLinkModal = () => {
    setLinkModalAccount(null);
    setLinkModalPortfolioId('');
    setLinkModalError('');
  };

  const saveLinkModal = async (e) => {
    e.preventDefault();
    if (!linkModalAccount) return;
    if (!linkModalPortfolioId) {
      setLinkModalError('Select a portfolio to link.');
      return;
    }
    setLinkModalSubmitting(true);
    setLinkModalError('');
    try {
      await updateBankAccount(
        linkModalAccount.id,
        portfolioPayload(linkModalPortfolioId)
      );
      const portfolioName =
        portfolios.find((p) => String(p.id) === linkModalPortfolioId)?.name ||
        'portfolio';
      setStatus(`Linked "${linkModalAccount.name}" to ${portfolioName}.`);
      closeLinkModal();
      await reload();
    } catch (err) {
      setLinkModalError(err.message || 'Failed to update portfolio link.');
    } finally {
      setLinkModalSubmitting(false);
    }
  };

  const handlePortfolioLink = async (account, portfolioId) => {
    setLinkSubmittingId(account.id);
    setError('');
    setStatus('');
    try {
      await updateBankAccount(account.id, portfolioPayload(portfolioId));
      setStatus(
        portfolioId
          ? `Linked "${account.name}" to portfolio.`
          : `Delinked "${account.name}" from portfolio.`
      );
      await reload();
    } catch (err) {
      setError(err.message || 'Failed to update portfolio link.');
    } finally {
      setLinkSubmittingId(null);
    }
  };

  const handleSeedOpeningBalance = async (account) => {
    setSeedingId(account.id);
    setError('');
    try {
      await seedBankAccountOpeningBalance(account.id);
      setStatus(`Opening balance seeded for "${account.name}".`);
      await reload();
      if (selectedAccountId === account.id) {
        setMovementsRefreshKey((k) => k + 1);
      }
    } catch (err) {
      setError(err.message || 'Failed to seed opening balance.');
    } finally {
      setSeedingId(null);
    }
  };

  const handleDeactivate = async (account) => {
    if (!window.confirm(`Deactivate bank account "${account.name}"?`)) return;
    setDeactivatingId(account.id);
    setError('');
    try {
      await deleteBankAccount(account.id);
      setStatus(`Bank account "${account.name}" deactivated.`);
      await reload();
    } catch (err) {
      setError(err.message || 'Failed to deactivate bank account.');
    } finally {
      setDeactivatingId(null);
    }
  };

  if (loading) return <p className="settings-hint">Loading bank accounts…</p>;

  return (
    <div className="bank-account-management">
      {status ? (
        <WarningBanner severity="success" message={status} className="settings-banner" />
      ) : null}
      {error ? (
        <WarningBanner severity="error" message={error} className="settings-banner" />
      ) : null}

      <p className="settings-hint">
        Bank account balances come from the cash movement ledger. You can optionally include
        ledger balance in portfolio value per account below. Use <strong>Linked portfolio</strong>{' '}
        to control where bank cash appears in Cash / Liquid Holdings — this does not move money.
      </p>

      {accounts.length > 0 ? (
        <div className="bank-account-table-wrap">
          <table className="bank-account-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Institution</th>
                <th>Account number</th>
                <th>Currency</th>
                <th>Current balance</th>
                <th>Linked portfolio</th>
                <th>In portfolio value</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id}>
                  <td>{account.name}</td>
                  <td>{account.institution_name}</td>
                  <td>{account.account_number}</td>
                  <td>{account.currency}</td>
                  <td>{account.current_balance}</td>
                  <td>{linkedPortfolioLabel(account)}</td>
                  <td>{account.include_in_portfolio_value ? 'Yes' : 'No'}</td>
                  <td>
                    {account.portfolio_id ? (
                      <>
                        <Button
                          variant="secondary"
                          type="button"
                          disabled={linkSubmittingId === account.id || linkModalSubmitting}
                          onClick={() => openLinkModal(account)}
                        >
                          Change linked portfolio
                        </Button>{' '}
                        <Button
                          variant="secondary"
                          type="button"
                          disabled={linkSubmittingId === account.id || linkModalSubmitting}
                          onClick={() => handlePortfolioLink(account, null)}
                        >
                          Delink from portfolio
                        </Button>{' '}
                      </>
                    ) : (
                      <Button
                        variant="secondary"
                        type="button"
                        disabled={linkSubmittingId === account.id || linkModalSubmitting}
                        onClick={() => openLinkModal(account)}
                      >
                        Link to portfolio
                      </Button>
                    )}{' '}
                    {account.opening_balance > 0 &&
                    !account.opening_balance_seeded &&
                    !account.has_ledger_entries ? (
                      <Button
                        variant="secondary"
                        type="button"
                        disabled={seedingId === account.id}
                        onClick={() => handleSeedOpeningBalance(account)}
                      >
                        Seed opening balance
                      </Button>
                    ) : null}{' '}
                    <Button
                      variant="secondary"
                      type="button"
                      onClick={() =>
                        setSelectedAccountId((id) => (id === account.id ? null : account.id))
                      }
                    >
                      {selectedAccountId === account.id ? 'Hide movements' : 'View movements'}
                    </Button>{' '}
                    <Button variant="secondary" type="button" onClick={() => startEdit(account)}>
                      Edit
                    </Button>{' '}
                    <Button
                      variant="secondary"
                      type="button"
                      disabled={deactivatingId === account.id}
                      onClick={() => handleDeactivate(account)}
                    >
                      Deactivate
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="settings-hint">No active bank accounts yet.</p>
      )}

      {selectedAccountId != null ? (
        <CashMovementManagement
          account={accounts.find((a) => a.id === selectedAccountId)}
          onAccountUpdated={reload}
          refreshKey={movementsRefreshKey}
        />
      ) : null}

      <form onSubmit={handleCreate} className="bank-account-form settings-form">
        <h3 className="bank-account-form__title">Add bank account</h3>
        <div className="form-group">
          <label htmlFor="ba-name">Name</label>
          <input
            id="ba-name"
            value={createForm.name}
            onChange={(e) => setCreateForm((p) => ({ ...p, name: e.target.value }))}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="ba-institution">Institution</label>
          <input
            id="ba-institution"
            value={createForm.institution_name}
            onChange={(e) => setCreateForm((p) => ({ ...p, institution_name: e.target.value }))}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="ba-account">Account number</label>
          <input
            id="ba-account"
            value={createForm.account_number}
            onChange={(e) => setCreateForm((p) => ({ ...p, account_number: e.target.value }))}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="ba-currency">Currency</label>
          <select
            id="ba-currency"
            value={createForm.currency}
            onChange={(e) => setCreateForm((p) => ({ ...p, currency: e.target.value }))}
          >
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="ba-portfolio">Linked portfolio (optional)</label>
          <select
            id="ba-portfolio"
            value={createForm.portfolio_id}
            onChange={(e) => setCreateForm((p) => ({ ...p, portfolio_id: e.target.value }))}
          >
            <option value="">Unlinked</option>
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <p className="settings-hint">{PORTFOLIO_LINK_HELP}</p>
        </div>
        <div className="form-group">
          <label htmlFor="ba-opening">Opening balance</label>
          <input
            id="ba-opening"
            type="number"
            step="0.01"
            value={createForm.opening_balance}
            onChange={(e) => setCreateForm((p) => ({ ...p, opening_balance: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="ba-current">Current balance (reference on create)</label>
          <input
            id="ba-current"
            type="number"
            step="0.01"
            value={createForm.current_balance}
            onChange={(e) => setCreateForm((p) => ({ ...p, current_balance: e.target.value }))}
          />
        </div>
        <p className="settings-hint">
          After the ledger is used, current balance is read-only and derived from cash movements.
        </p>
        <div className="form-group">
          <label htmlFor="ba-comment">Comment</label>
          <textarea
            id="ba-comment"
            value={createForm.comment}
            onChange={(e) => setCreateForm((p) => ({ ...p, comment: e.target.value }))}
            rows={2}
          />
        </div>
        <Button type="submit" variant="primary" disabled={createSubmitting}>
          {createSubmitting ? 'Creating…' : 'Add bank account'}
        </Button>
      </form>

      {editingId != null ? (
        <form onSubmit={handleEdit} className="bank-account-form settings-form">
          <h3 className="bank-account-form__title">Edit bank account</h3>
          <div className="form-group">
            <label htmlFor="ba-edit-portfolio">Linked portfolio</label>
            <select
              id="ba-edit-portfolio"
              value={editForm.portfolio_id}
              onChange={(e) => setEditForm((p) => ({ ...p, portfolio_id: e.target.value }))}
            >
              <option value="">Unlinked</option>
              {portfolios.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <p className="settings-hint">{PORTFOLIO_LINK_HELP}</p>
            {(accounts.find((a) => a.id === editingId)?.active_fixed_deposit_count ?? 0) > 0 ? (
              <WarningBanner
                severity="warning"
                message="This bank account has linked Fixed Deposits. Changing the link affects where bank cash appears, but does not rewrite existing FD records."
                className="settings-banner"
              />
            ) : null}
          </div>
          <div className="form-group">
            <label htmlFor="ba-edit-name">Name</label>
            <input
              id="ba-edit-name"
              value={editForm.name}
              onChange={(e) => setEditForm((p) => ({ ...p, name: e.target.value }))}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="ba-edit-institution">Institution</label>
            <input
              id="ba-edit-institution"
              value={editForm.institution_name}
              onChange={(e) => setEditForm((p) => ({ ...p, institution_name: e.target.value }))}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="ba-edit-account">Account number</label>
            <input
              id="ba-edit-account"
              value={editForm.account_number}
              onChange={(e) => setEditForm((p) => ({ ...p, account_number: e.target.value }))}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="ba-edit-currency">Currency</label>
            <select
              id="ba-edit-currency"
              value={editForm.currency}
              onChange={(e) => setEditForm((p) => ({ ...p, currency: e.target.value }))}
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="ba-edit-opening">Opening balance</label>
            <input
              id="ba-edit-opening"
              type="number"
              step="0.01"
              value={editForm.opening_balance}
              onChange={(e) => setEditForm((p) => ({ ...p, opening_balance: e.target.value }))}
            />
          </div>
          <div className="form-group">
            <label htmlFor="ba-edit-current">Current balance</label>
            {accounts.find((a) => a.id === editingId)?.has_ledger_entries ? (
              <p id="ba-edit-current" className="settings-hint">
                {editForm.current_balance} (ledger-derived — read only)
              </p>
            ) : (
              <input
                id="ba-edit-current"
                type="number"
                step="0.01"
                value={editForm.current_balance}
                onChange={(e) => setEditForm((p) => ({ ...p, current_balance: e.target.value }))}
              />
            )}
          </div>
          <div className="form-group">
            <label htmlFor="ba-edit-include">
              <input
                id="ba-edit-include"
                type="checkbox"
                checked={editForm.include_in_portfolio_value}
                onChange={(e) =>
                  setEditForm((p) => ({
                    ...p,
                    include_in_portfolio_value: e.target.checked,
                  }))
                }
              />{' '}
              Include this bank cash in portfolio value
            </label>
            <p className="settings-hint">
              When enabled, the ledger balance of this bank account is included as Cash in
              portfolio value. Manual/reference balances are not included until seeded into the
              ledger.
            </p>
            {editForm.include_in_portfolio_value &&
            !accounts.find((a) => a.id === editingId)?.has_ledger_entries ? (
              <WarningBanner
                severity="warning"
                message="This account has no ledger entries yet. Portfolio value will include 0 until you seed the opening balance or record a movement."
                className="settings-banner"
              />
            ) : null}
          </div>
          <div className="form-group">
            <label htmlFor="ba-edit-comment">Comment</label>
            <textarea
              id="ba-edit-comment"
              value={editForm.comment}
              onChange={(e) => setEditForm((p) => ({ ...p, comment: e.target.value }))}
              rows={2}
            />
          </div>
          <div className="bank-account-form__actions">
            <Button type="submit" variant="primary" disabled={editSubmitting}>
              {editSubmitting ? 'Saving…' : 'Save changes'}
            </Button>
            <Button type="button" variant="secondary" onClick={() => setEditingId(null)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : null}

      {linkModalAccount ? (
        <div
          className="cash-movement-modal-backdrop"
          role="presentation"
          onClick={closeLinkModal}
        >
          <div
            className="cash-movement-modal bank-account-link-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bank-account-link-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="bank-account-link-modal-title">
              {linkModalAccount.portfolio_id ? 'Change linked portfolio' : 'Link to portfolio'}
            </h2>
            <p className="settings-hint">
              Account: <strong>{linkModalAccount.name}</strong>
            </p>
            <p className="settings-hint">{PORTFOLIO_LINK_HELP}</p>
            {(linkModalAccount.active_fixed_deposit_count ?? 0) > 0 ? (
              <WarningBanner
                severity="warning"
                message="This bank account has linked Fixed Deposits. Changing the link affects where bank cash appears, but does not rewrite existing FD records."
                className="settings-banner"
              />
            ) : null}
            {linkModalError ? (
              <WarningBanner severity="error" message={linkModalError} className="settings-banner" />
            ) : null}
            <form onSubmit={saveLinkModal}>
              <div className="form-group">
                <label htmlFor="bank-account-link-portfolio">Linked portfolio</label>
                {portfolios.length === 0 ? (
                  <p className="settings-hint">
                    No active portfolios available. Create a portfolio in Settings → Portfolios
                    first.
                  </p>
                ) : (
                  <select
                    id="bank-account-link-portfolio"
                    value={linkModalPortfolioId}
                    onChange={(e) => setLinkModalPortfolioId(e.target.value)}
                    required
                    disabled={linkModalSubmitting}
                  >
                    <option value="">Select portfolio</option>
                    {portfolios.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <div className="cash-movement-modal__actions">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={linkModalSubmitting || portfolios.length === 0}
                >
                  {linkModalSubmitting ? 'Saving…' : 'Save link'}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={closeLinkModal}
                  disabled={linkModalSubmitting}
                >
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
