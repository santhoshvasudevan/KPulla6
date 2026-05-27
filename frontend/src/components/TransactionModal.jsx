import { useState, useEffect } from 'react';
import { createTransaction, updateTransaction } from '../api';
import { Button, StatusBadge } from './ui';
import { navVerificationBadgeStatus, navVerificationLabel } from '../utils/transactionDisplay';
import './TransactionModal.css';
import { usePortfolio } from '../portfolioContext';

const STOCK_TYPES = ['BUY', 'SELL', 'DIVIDEND', 'STOCK_SPLIT'];
const MF_TYPES = ['BUY', 'SELL'];

function emptyStockForm(portfolioId = '') {
  return {
    portfolio_id: portfolioId,
    asset_symbol: '',
    date: new Date().toISOString().split('T')[0],
    type: 'BUY',
    quantity: '',
    price_per_share: '',
    currency: 'EUR',
    fees: '0',
    split_from: '',
    split_to: '',
  };
}

function emptyMutualFundForm(portfolioId = '') {
  return {
    portfolio_id: portfolioId,
    scheme_code: '',
    scheme_name: '',
    folio_number: '',
    type: 'BUY',
    investment_date: new Date().toISOString().split('T')[0],
    nav_date: new Date().toISOString().split('T')[0],
    nav: '',
    units_allotted: '',
    paid_value: '',
    market_value: '',
    currency: 'INR',
    fees: '',
    fund_house: '',
    scheme_type: '',
    scheme_category: '',
    direct_or_regular: '',
    growth_or_idcw: '',
  };
}

function stockFormFromTransaction(txn) {
  return {
    portfolio_id: txn.portfolio_id != null ? String(txn.portfolio_id) : '',
    asset_symbol: txn.asset_symbol,
    date: txn.date,
    type: txn.type,
    quantity: String(txn.quantity ?? ''),
    price_per_share: String(txn.price_per_share ?? ''),
    currency: txn.currency,
    fees: String(txn.fees ?? '0'),
    split_from: txn.split_from?.toString() || '',
    split_to: txn.split_to?.toString() || '',
  };
}

function mutualFundFormFromTransaction(txn) {
  return {
    portfolio_id: txn.portfolio_id != null ? String(txn.portfolio_id) : '',
    scheme_code: txn.scheme_code || txn.asset_symbol || '',
    scheme_name: txn.scheme_name || '',
    folio_number: txn.folio_number || '',
    type: txn.type,
    investment_date: txn.investment_date || txn.date || '',
    nav_date: txn.nav_date || txn.date || '',
    nav: String(txn.nav ?? txn.price_per_share ?? ''),
    units_allotted: String(txn.units_allotted ?? txn.quantity ?? ''),
    paid_value: String(txn.paid_value ?? ''),
    market_value: String(txn.market_value ?? ''),
    currency: txn.currency || 'INR',
    fees: txn.fees != null ? String(txn.fees) : '',
    fund_house: txn.fund_house || '',
    scheme_type: txn.scheme_type || '',
    scheme_category: txn.scheme_category || '',
    direct_or_regular: txn.direct_or_regular || '',
    growth_or_idcw: txn.growth_or_idcw || '',
  };
}

function parseOptionalNumber(value) {
  if (value === '' || value == null) return undefined;
  const n = parseFloat(value);
  return Number.isNaN(n) ? undefined : n;
}

function validateMutualFundForm(form) {
  const required = [
    ['scheme_code', 'Scheme code'],
    ['scheme_name', 'Scheme name'],
    ['folio_number', 'Folio number'],
    ['investment_date', 'Investment date'],
    ['nav_date', 'NAV date'],
    ['nav', 'NAV'],
    ['units_allotted', 'Units allotted'],
    ['paid_value', 'Paid value'],
    ['market_value', 'Market value'],
  ];
  for (const [key, label] of required) {
    if (!String(form[key] ?? '').trim()) return `${label} is required`;
  }
  const nav = parseFloat(form.nav);
  const units = parseFloat(form.units_allotted);
  const paid = parseFloat(form.paid_value);
  const market = parseFloat(form.market_value);
  if (!(nav > 0)) return 'NAV must be greater than 0';
  if (!(units > 0)) return 'Units allotted must be greater than 0';
  if (Number.isNaN(paid) || paid < 0) return 'Paid value must be zero or positive';
  if (Number.isNaN(market) || market < 0) return 'Market value must be zero or positive';
  return null;
}

function buildStockPayload(formData) {
  const isStockSplit = formData.type === 'STOCK_SPLIT';
  return {
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
}

function buildMutualFundPayload(formData) {
  const payload = {
    asset_type: 'MUTUAL_FUND',
    scheme_code: formData.scheme_code.trim(),
    scheme_name: formData.scheme_name.trim(),
    folio_number: formData.folio_number.trim(),
    type: formData.type,
    investment_date: formData.investment_date,
    nav_date: formData.nav_date,
    nav: parseFloat(formData.nav),
    units_allotted: parseFloat(formData.units_allotted),
    paid_value: parseFloat(formData.paid_value),
    market_value: parseFloat(formData.market_value),
    currency: formData.currency || 'INR',
    portfolio_id: formData.portfolio_id ? Number(formData.portfolio_id) : null,
  };
  const fees = parseOptionalNumber(formData.fees);
  if (fees !== undefined) payload.fees = fees;
  const optionalStrings = [
    'fund_house',
    'scheme_type',
    'scheme_category',
    'direct_or_regular',
    'growth_or_idcw',
  ];
  for (const key of optionalStrings) {
    const v = String(formData[key] ?? '').trim();
    if (v) payload[key] = v;
  }
  return payload;
}

export default function TransactionModal({ isOpen, onClose, onSuccess, initialData }) {
  const isEditing = !!initialData;
  const { portfolios, selectedPortfolioMode, selectedPortfolioId } = usePortfolio();
  const activePortfolios = (portfolios || []).filter((p) => p && p.is_active);
  const defaultPortfolioId = activePortfolios.find((p) => p.is_default)?.id ?? null;

  const [assetType, setAssetType] = useState('STOCK');
  const [stockForm, setStockForm] = useState(emptyStockForm());
  const [mfForm, setMfForm] = useState(emptyMutualFundForm());

  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const suggested =
      selectedPortfolioMode === 'portfolio' && selectedPortfolioId != null
        ? String(selectedPortfolioId)
        : defaultPortfolioId != null
          ? String(defaultPortfolioId)
          : '';

    if (initialData?.asset_type === 'MUTUAL_FUND') {
      setAssetType('MUTUAL_FUND');
      setMfForm(mutualFundFormFromTransaction(initialData));
      setStockForm(emptyStockForm(suggested));
    } else if (initialData) {
      setAssetType('STOCK');
      setStockForm(stockFormFromTransaction(initialData));
      setMfForm(emptyMutualFundForm(suggested));
    } else {
      setAssetType('STOCK');
      setStockForm(emptyStockForm(suggested));
      setMfForm(emptyMutualFundForm(suggested));
    }
    setError('');
  }, [isOpen, initialData, selectedPortfolioMode, selectedPortfolioId, defaultPortfolioId]);

  if (!isOpen) return null;

  const isMutualFund = assetType === 'MUTUAL_FUND';

  const handleStockChange = (e) => {
    const { name, value } = e.target;
    setStockForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleMfChange = (e) => {
    const { name, value } = e.target;
    setMfForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleAssetTypeChange = (e) => {
    if (isEditing) return;
    const next = e.target.value;
    setAssetType(next);
    const portfolioId =
      next === 'MUTUAL_FUND' ? mfForm.portfolio_id : stockForm.portfolio_id;
    if (next === 'MUTUAL_FUND' && !mfForm.portfolio_id) {
      setMfForm((prev) => ({ ...prev, portfolio_id: portfolioId || stockForm.portfolio_id }));
    }
    if (next === 'STOCK' && !stockForm.portfolio_id) {
      setStockForm((prev) => ({ ...prev, portfolio_id: portfolioId || mfForm.portfolio_id }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      if (isMutualFund) {
        const validationError = validateMutualFundForm(mfForm);
        if (validationError) {
          setError(validationError);
          setSubmitting(false);
          return;
        }
        const payload = buildMutualFundPayload(mfForm);
        if (isEditing) {
          await updateTransaction(initialData.id, payload);
        } else {
          await createTransaction(payload);
        }
      } else {
        const isStockSplit = stockForm.type === 'STOCK_SPLIT';
        if (isStockSplit) {
          const splitFrom = parseFloat(stockForm.split_from);
          const splitTo = parseFloat(stockForm.split_to);
          if (!(splitFrom > 0) || !(splitTo > 0)) {
            setError('split_from and split_to must be greater than 0');
            setSubmitting(false);
            return;
          }
        }
        const payload = buildStockPayload(stockForm);
        if (isEditing) {
          await updateTransaction(initialData.id, payload);
        } else {
          await createTransaction(payload);
        }
      }
      onSuccess();
      onClose();
    } catch (err) {
      setError(err.message || 'Save failed');
    } finally {
      setSubmitting(false);
    }
  };

  const navStatus = initialData?.nav_verification_status;
  const navMessage = initialData?.nav_verification_message;

  return (
    <div className="modal-overlay">
      <div className={`modal-content${isMutualFund ? ' modal-content--wide' : ''}`}>
        <h3>{isEditing ? 'Edit Transaction' : 'Add Transaction'}</h3>
        {error && <div className="modal-error">{error}</div>}

        <form className="modal-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Asset type</label>
            <select
              aria-label="asset type"
              name="asset_type"
              value={assetType}
              onChange={handleAssetTypeChange}
              disabled={isEditing}
            >
              <option value="STOCK">Stock</option>
              <option value="MUTUAL_FUND">Mutual fund</option>
            </select>
          </div>

          <div className="form-group">
            <label>Portfolio</label>
            <select
              aria-label="portfolio"
              name="portfolio_id"
              value={isMutualFund ? mfForm.portfolio_id : stockForm.portfolio_id}
              onChange={isMutualFund ? handleMfChange : handleStockChange}
              required
            >
              {activePortfolios.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {isMutualFund ? (
            <>
              {isEditing && navStatus ? (
                <div className="modal-nav-status">
                  <StatusBadge
                    status={navVerificationBadgeStatus(navStatus)}
                    label={navVerificationLabel(navStatus)}
                  />
                  {navMessage ? (
                    <p className="modal-nav-status__message">{navMessage}</p>
                  ) : null}
                </div>
              ) : null}

              <div className="form-row">
                <div className="form-group">
                  <label>Scheme code</label>
                  <input
                    type="text"
                    name="scheme_code"
                    value={mfForm.scheme_code}
                    onChange={handleMfChange}
                    required
                    disabled={isEditing}
                  />
                </div>
                <div className="form-group">
                  <label>Scheme name</label>
                  <input
                    type="text"
                    name="scheme_name"
                    value={mfForm.scheme_name}
                    onChange={handleMfChange}
                    required
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Folio number</label>
                  <input
                    type="text"
                    name="folio_number"
                    value={mfForm.folio_number}
                    onChange={handleMfChange}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Type</label>
                  <select name="type" value={mfForm.type} onChange={handleMfChange} required>
                    {MF_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Investment date</label>
                  <input
                    type="date"
                    name="investment_date"
                    value={mfForm.investment_date}
                    onChange={handleMfChange}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>NAV date</label>
                  <input
                    type="date"
                    name="nav_date"
                    value={mfForm.nav_date}
                    onChange={handleMfChange}
                    required
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>NAV</label>
                  <input
                    type="number"
                    step="any"
                    name="nav"
                    value={mfForm.nav}
                    onChange={handleMfChange}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Units allotted</label>
                  <input
                    type="number"
                    step="any"
                    name="units_allotted"
                    value={mfForm.units_allotted}
                    onChange={handleMfChange}
                    required
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Paid value</label>
                  <input
                    type="number"
                    step="any"
                    name="paid_value"
                    value={mfForm.paid_value}
                    onChange={handleMfChange}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Market value</label>
                  <input
                    type="number"
                    step="any"
                    name="market_value"
                    value={mfForm.market_value}
                    onChange={handleMfChange}
                    required
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Currency</label>
                  <input
                    type="text"
                    name="currency"
                    value={mfForm.currency}
                    onChange={handleMfChange}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Fees (optional)</label>
                  <input
                    type="number"
                    step="any"
                    name="fees"
                    value={mfForm.fees}
                    onChange={handleMfChange}
                  />
                </div>
              </div>

              <details className="modal-mf-optional">
                <summary>Optional scheme metadata</summary>
                <div className="form-row">
                  <div className="form-group">
                    <label>Fund house</label>
                    <input
                      type="text"
                      name="fund_house"
                      value={mfForm.fund_house}
                      onChange={handleMfChange}
                    />
                  </div>
                  <div className="form-group">
                    <label>Scheme type</label>
                    <input
                      type="text"
                      name="scheme_type"
                      value={mfForm.scheme_type}
                      onChange={handleMfChange}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Scheme category</label>
                    <input
                      type="text"
                      name="scheme_category"
                      value={mfForm.scheme_category}
                      onChange={handleMfChange}
                    />
                  </div>
                  <div className="form-group">
                    <label>Direct or regular</label>
                    <input
                      type="text"
                      name="direct_or_regular"
                      value={mfForm.direct_or_regular}
                      onChange={handleMfChange}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Growth or IDCW</label>
                  <input
                    type="text"
                    name="growth_or_idcw"
                    value={mfForm.growth_or_idcw}
                    onChange={handleMfChange}
                  />
                </div>
              </details>
            </>
          ) : (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label>Asset Symbol</label>
                  <input
                    type="text"
                    name="asset_symbol"
                    value={stockForm.asset_symbol}
                    onChange={handleStockChange}
                    required
                    disabled={isEditing}
                  />
                </div>
                <div className="form-group">
                  <label>Date</label>
                  <input
                    type="date"
                    name="date"
                    value={stockForm.date}
                    onChange={handleStockChange}
                    required
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Type</label>
                  <select name="type" value={stockForm.type} onChange={handleStockChange} required>
                    {STOCK_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Currency</label>
                  <input
                    type="text"
                    name="currency"
                    value={stockForm.currency}
                    onChange={handleStockChange}
                    required={stockForm.type !== 'STOCK_SPLIT'}
                    disabled={stockForm.type === 'STOCK_SPLIT'}
                  />
                </div>
              </div>

              {stockForm.type !== 'STOCK_SPLIT' && (
                <>
                  <div className="form-row">
                    <div className="form-group">
                      <label>Quantity</label>
                      <input
                        type="number"
                        step="any"
                        name="quantity"
                        value={stockForm.quantity}
                        onChange={handleStockChange}
                        required
                      />
                    </div>
                    <div className="form-group">
                      <label>Price / Share</label>
                      <input
                        type="number"
                        step="any"
                        name="price_per_share"
                        value={stockForm.price_per_share}
                        onChange={handleStockChange}
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
                      value={stockForm.fees}
                      onChange={handleStockChange}
                      required
                    />
                  </div>
                </>
              )}

              {stockForm.type === 'STOCK_SPLIT' && (
                <div className="form-row">
                  <div className="form-group">
                    <label>split_from</label>
                    <input
                      type="number"
                      step="any"
                      name="split_from"
                      value={stockForm.split_from}
                      onChange={handleStockChange}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>split_to</label>
                    <input
                      type="number"
                      step="any"
                      name="split_to"
                      value={stockForm.split_to}
                      onChange={handleStockChange}
                      required
                    />
                  </div>
                </div>
              )}
            </>
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
