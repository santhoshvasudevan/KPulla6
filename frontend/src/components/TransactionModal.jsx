import { useState, useEffect } from 'react';
import { createTransaction, updateTransaction } from '../api';
import { Button } from './ui';
import './TransactionModal.css';
import { usePortfolio } from '../portfolioContext';

export default function TransactionModal({ isOpen, onClose, onSuccess, initialData }) {
  const isEditing = !!initialData;
  const { portfolios, selectedPortfolioMode, selectedPortfolioId } = usePortfolio();
  const activePortfolios = (portfolios || []).filter((p) => p && p.is_active);
  const defaultPortfolioId = activePortfolios.find((p) => p.is_default)?.id ?? null;

  const [formData, setFormData] = useState({
    portfolio_id: '',
    asset_symbol: '',
    date: new Date().toISOString().split('T')[0],
    type: 'BUY',
    quantity: '',
    price_per_share: '',
    currency: 'EUR',
    fees: '0',
    split_from: '',
    split_to: '',
  });

  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    if (initialData) {
      setFormData({
        portfolio_id: initialData.portfolio_id != null ? String(initialData.portfolio_id) : '',
        asset_symbol: initialData.asset_symbol,
        date: initialData.date,
        type: initialData.type,
        quantity: String(initialData.quantity ?? ''),
        price_per_share: String(initialData.price_per_share ?? ''),
        currency: initialData.currency,
        fees: String(initialData.fees ?? '0'),
        split_from: initialData.split_from?.toString() || '',
        split_to: initialData.split_to?.toString() || '',
      });
    } else {
      const suggested =
        selectedPortfolioMode === 'portfolio' && selectedPortfolioId != null
          ? String(selectedPortfolioId)
          : defaultPortfolioId != null
            ? String(defaultPortfolioId)
            : '';
      setFormData({
        portfolio_id: suggested,
        asset_symbol: '',
        date: new Date().toISOString().split('T')[0],
        type: 'BUY',
        quantity: '',
        price_per_share: '',
        currency: 'EUR',
        fees: '0',
        split_from: '',
        split_to: '',
      });
    }
    setError('');
  }, [isOpen, initialData, selectedPortfolioMode, selectedPortfolioId, defaultPortfolioId]);

  if (!isOpen) return null;

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    const isStockSplit = formData.type === 'STOCK_SPLIT';
    if (isStockSplit) {
      const splitFrom = parseFloat(formData.split_from);
      const splitTo = parseFloat(formData.split_to);
      if (!(splitFrom > 0) || !(splitTo > 0)) {
        setError('split_from and split_to must be greater than 0');
        setSubmitting(false);
        return;
      }
    }

    const payload = {
      asset_symbol: formData.asset_symbol,
      date: formData.date,
      type: formData.type,
      currency: formData.currency,
      portfolio_id: formData.portfolio_id ? Number(formData.portfolio_id) : null,
      quantity: isStockSplit ? 0 : parseFloat(formData.quantity),
      price_per_share: isStockSplit ? 0 : parseFloat(formData.price_per_share),
      fees: isStockSplit ? 0 : parseFloat(formData.fees || 0),
      split_from: isStockSplit ? parseFloat(formData.split_from) : null,
      split_to: isStockSplit ? parseFloat(formData.split_to) : null,
    };

    try {
      if (isEditing) {
        await updateTransaction(initialData.id, payload);
      } else {
        await createTransaction(payload);
      }
      onSuccess();
      onClose();
    } catch (err) {
      setError(err.message || 'Save failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h3>{isEditing ? 'Edit Transaction' : 'Add Transaction'}</h3>
        {error && <div className="modal-error">{error}</div>}

        <form className="modal-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Portfolio</label>
            <select
              aria-label="portfolio"
              name="portfolio_id"
              value={formData.portfolio_id}
              onChange={handleChange}
              required
            >
              {activePortfolios.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Asset Symbol</label>
              <input
                type="text"
                name="asset_symbol"
                value={formData.asset_symbol}
                onChange={handleChange}
                required
                disabled={isEditing}
              />
            </div>
            <div className="form-group">
              <label>Date</label>
              <input type="date" name="date" value={formData.date} onChange={handleChange} required />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Type</label>
              <select name="type" value={formData.type} onChange={handleChange} required>
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
                <option value="DIVIDEND">DIVIDEND</option>
                <option value="STOCK_SPLIT">STOCK_SPLIT</option>
              </select>
            </div>
            <div className="form-group">
              <label>Currency</label>
              <input
                type="text"
                name="currency"
                value={formData.currency}
                onChange={handleChange}
                required={formData.type !== 'STOCK_SPLIT'}
                disabled={formData.type === 'STOCK_SPLIT'}
              />
            </div>
          </div>

          {formData.type !== 'STOCK_SPLIT' && (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label>Quantity</label>
                  <input
                    type="number"
                    step="any"
                    name="quantity"
                    value={formData.quantity}
                    onChange={handleChange}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Price / Share</label>
                  <input
                    type="number"
                    step="any"
                    name="price_per_share"
                    value={formData.price_per_share}
                    onChange={handleChange}
                    required
                  />
                </div>
              </div>
              <div className="form-group">
                <label>Fees</label>
                <input
                  type="number"
                  step="any"
                  name="fees"
                  value={formData.fees}
                  onChange={handleChange}
                  required
                />
              </div>
            </>
          )}

          {formData.type === 'STOCK_SPLIT' && (
            <div className="form-row">
              <div className="form-group">
                <label>split_from</label>
                <input
                  type="number"
                  step="any"
                  name="split_from"
                  value={formData.split_from}
                  onChange={handleChange}
                  required
                />
              </div>
              <div className="form-group">
                <label>split_to</label>
                <input
                  type="number"
                  step="any"
                  name="split_to"
                  value={formData.split_to}
                  onChange={handleChange}
                  required
                />
              </div>
            </div>
          )}

          <div className="modal-actions">
            <Button type="button" variant="secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
