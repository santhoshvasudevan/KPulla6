import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  createTransaction,
  updateTransaction,
  createCashDeposit,
  createCashWithdrawal,
  ApiError,
  futureImpactFromApiError,
} from '../api';
import { Button, StatusBadge } from './ui';
import { navVerificationBadgeStatus, navVerificationLabel } from '../utils/transactionDisplay';
import CashEntryFormFields, { emptyCashForm } from './CashEntryFormFields';
import CashShortfallDisplay from './CashShortfallDisplay';
import CashFutureImpactDisplay, {
  TRANSACTION_FUTURE_IMPACT_INTRO,
  TRANSACTION_FUTURE_IMPACT_HELPER,
} from './CashFutureImpactDisplay';
import PurchaseShortfallAction from './PurchaseShortfallAction';
import './CashFutureImpactDisplay.css';
import { buildShortfallDepositPayload } from '../utils/purchaseShortfallHelpers';
import './TransactionModal.css';
import { usePortfolio } from '../portfolioContext';

const PARTIAL_PURCHASE_WARNING =
  'Cash deposit was created, but the purchase could not be recorded. Please review and try again.';

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
    actual_cash_received: '',
    settlement_note: '',
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
    actual_cash_received: '',
    settlement_note: '',
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
    actual_cash_received:
      txn.actual_cash_received != null ? String(txn.actual_cash_received) : '',
    settlement_note: txn.settlement_note || '',
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
    actual_cash_received:
      txn.actual_cash_received != null ? String(txn.actual_cash_received) : '',
    settlement_note: txn.settlement_note || '',
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

function previewStockCalculatedProceeds(form) {
  const qty = parseFloat(form.quantity);
  const price = parseFloat(form.price_per_share);
  const fees = parseFloat(form.fees || 0);
  if (Number.isNaN(qty) || Number.isNaN(price)) return null;
  const feeValue = Number.isNaN(fees) ? 0 : fees;
  const proceeds = qty * price - feeValue;
  return proceeds > 0 ? proceeds : null;
}

function previewMfCalculatedProceeds(form) {
  const paid = parseFloat(form.paid_value);
  const units = parseFloat(form.units_allotted);
  const nav = parseFloat(form.nav);
  const fees = parseFloat(form.fees || 0);
  if (!Number.isNaN(paid) && paid > 0) return paid;
  if (Number.isNaN(units) || Number.isNaN(nav)) return null;
  const feeValue = Number.isNaN(fees) ? 0 : fees;
  const proceeds = units * nav - feeValue;
  return proceeds > 0 ? proceeds : null;
}

function previewTaxWithheld(calculated, actualRaw) {
  if (calculated == null || actualRaw === '' || actualRaw == null) return null;
  const actual = parseFloat(actualRaw);
  if (Number.isNaN(actual) || actual <= 0) return null;
  const withheld = calculated - actual;
  return withheld > 0 ? withheld : 0;
}

function appendSellSettlementFields(payload, form) {
  const actual = parseOptionalNumber(form.actual_cash_received);
  if (actual !== undefined) payload.actual_cash_received = actual;
  const note = String(form.settlement_note ?? '').trim();
  if (note) payload.settlement_note = note;
  return payload;
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
  if (formData.type === 'SELL') {
    appendSellSettlementFields(payload, formData);
  }
  return payload;
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
  if (formData.type === 'SELL') {
    appendSellSettlementFields(payload, formData);
  }
  return payload;
}

function buildCashWritePayload(form, portfolioId) {
  return {
    portfolio_id: portfolioId,
    date: form.date,
    currency: form.currency,
    amount: parseFloat(form.amount),
    note: form.note || '',
    source_of_funds: form.source_of_funds || '',
  };
}

function shortfallFromApiError(err) {
  if (
    !(err instanceof ApiError) ||
    err.required == null ||
    err.available == null ||
    err.shortfall == null
  ) {
    return null;
  }
  return {
    required: err.required,
    available: err.available,
    shortfall: err.shortfall,
    currency: err.currency,
  };
}

export default function TransactionModal({ isOpen, onClose, onSuccess, initialData }) {
  const isEditing = !!initialData;
  const { portfolios, selectedPortfolioMode, selectedPortfolioId } = usePortfolio();
  const activePortfolios = (portfolios || []).filter((p) => p && p.is_active);
  const defaultPortfolioId = activePortfolios.find((p) => p.is_default)?.id ?? null;
  const isAllScope = selectedPortfolioMode === 'all';
  const requirePortfolioPick = isAllScope;

  const [recordType, setRecordType] = useState('STOCK');
  const [cashAction, setCashAction] = useState('deposit');
  const [stockForm, setStockForm] = useState(emptyStockForm());
  const [mfForm, setMfForm] = useState(emptyMutualFundForm());
  const [cashForm, setCashForm] = useState(emptyCashForm());

  const [error, setError] = useState('');
  const [partialWarning, setPartialWarning] = useState('');
  const [shortfall, setShortfall] = useState(null);
  const [pendingAssetSubmit, setPendingAssetSubmit] = useState(null);
  const [shortfallDeposit, setShortfallDeposit] = useState({ source_of_funds: '', note: '' });
  const [futureImpact, setFutureImpact] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [addAndContinueLoading, setAddAndContinueLoading] = useState(false);
  const addAndContinueInFlight = useRef(false);

  useEffect(() => {
    if (!isOpen) return;
    const suggested =
      selectedPortfolioMode === 'portfolio' && selectedPortfolioId != null
        ? String(selectedPortfolioId)
        : defaultPortfolioId != null
          ? String(defaultPortfolioId)
          : '';

    const cashPortfolioDefault =
      selectedPortfolioMode === 'portfolio' && selectedPortfolioId != null
        ? String(selectedPortfolioId)
        : selectedPortfolioMode === 'all'
          ? ''
          : suggested;

    if (initialData?.asset_type === 'MUTUAL_FUND') {
      setRecordType('MUTUAL_FUND');
      setMfForm(mutualFundFormFromTransaction(initialData));
      setStockForm(emptyStockForm(suggested));
    } else if (initialData) {
      setRecordType('STOCK');
      setStockForm(stockFormFromTransaction(initialData));
      setMfForm(emptyMutualFundForm(suggested));
    } else {
      setRecordType('STOCK');
      setStockForm(emptyStockForm(suggested));
      setMfForm(emptyMutualFundForm(suggested));
      setCashForm(emptyCashForm(cashPortfolioDefault));
      setCashAction('deposit');
    }
    setError('');
    setPartialWarning('');
    setShortfall(null);
    setFutureImpact(null);
    setPendingAssetSubmit(null);
    setShortfallDeposit({ source_of_funds: '', note: '' });
    setAddAndContinueLoading(false);
    addAndContinueInFlight.current = false;
  }, [isOpen, initialData, selectedPortfolioMode, selectedPortfolioId, defaultPortfolioId]);

  if (!isOpen) return null;

  const isCash = recordType === 'CASH';
  const isMutualFund = recordType === 'MUTUAL_FUND';

  const handleStockChange = (e) => {
    const { name, value } = e.target;
    setStockForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleMfChange = (e) => {
    const { name, value } = e.target;
    setMfForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleCashFieldChange = (field, value) => {
    setCashForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleRecordTypeChange = (e) => {
    if (isEditing) return;
    const next = e.target.value;
    setRecordType(next);
    const portfolioId =
      next === 'MUTUAL_FUND'
        ? mfForm.portfolio_id
        : next === 'CASH'
          ? cashForm.portfolio_id
          : stockForm.portfolio_id;
    const shared = portfolioId || stockForm.portfolio_id || mfForm.portfolio_id || cashForm.portfolio_id;
    if (next === 'MUTUAL_FUND' && !mfForm.portfolio_id) {
      setMfForm((prev) => ({ ...prev, portfolio_id: shared }));
    }
    if (next === 'STOCK' && !stockForm.portfolio_id) {
      setStockForm((prev) => ({ ...prev, portfolio_id: shared }));
    }
    if (next === 'CASH') {
      setCashForm((prev) => ({
        ...prev,
        portfolio_id:
          prev.portfolio_id || (requirePortfolioPick ? '' : shared),
      }));
    }
  };

  const resolveCashPortfolioId = () => {
    if (requirePortfolioPick) {
      return Number(cashForm.portfolio_id);
    }
    if (cashForm.portfolio_id) {
      return Number(cashForm.portfolio_id);
    }
    if (activePortfolios.length === 1) {
      return activePortfolios[0].id;
    }
    return NaN;
  };

  const isAssetBuy =
    !isCash &&
    ((isMutualFund && mfForm.type === 'BUY') || (!isMutualFund && stockForm.type === 'BUY'));

  const showPurchaseShortfallAction =
    shortfall && isAssetBuy && pendingAssetSubmit != null;

  const busy = submitting || addAndContinueLoading;

  const storeBuyShortfall = (apiShortfall, assetSubmit) => {
    setError('Insufficient cash balance for purchase.');
    setPartialWarning('');
    setFutureImpact(null);
    setShortfall(apiShortfall);
    setPendingAssetSubmit(assetSubmit);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setPartialWarning('');
    setShortfall(null);
    setFutureImpact(null);
    setPendingAssetSubmit(null);
    setSubmitting(true);

    try {
      if (isCash) {
        const portfolioId = resolveCashPortfolioId();
        if (!portfolioId || Number.isNaN(portfolioId)) {
          setError('Select a portfolio.');
          setSubmitting(false);
          return;
        }
        const amount = parseFloat(cashForm.amount);
        if (!cashForm.amount || Number.isNaN(amount) || amount <= 0) {
          setError('Enter an amount greater than zero.');
          setSubmitting(false);
          return;
        }
        const payload = buildCashWritePayload(cashForm, portfolioId);
        if (cashAction === 'deposit') {
          await createCashDeposit(payload);
          onSuccess?.({ kind: 'cash', message: 'Deposit recorded.' });
        } else {
          await createCashWithdrawal(payload);
          onSuccess?.({ kind: 'cash', message: 'Withdrawal recorded.' });
        }
      } else if (isMutualFund) {
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
        onSuccess?.({ kind: 'asset' });
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
        onSuccess?.({ kind: 'asset' });
      }
      onClose();
    } catch (err) {
      const apiShortfall = shortfallFromApiError(err);
      if (apiShortfall && isCash && cashAction === 'withdrawal') {
        setError('Insufficient cash balance for withdrawal.');
        setShortfall(apiShortfall);
      } else if (apiShortfall && isAssetBuy) {
        const assetSubmit = isMutualFund
          ? {
              mode: isEditing ? 'update' : 'create',
              transactionId: initialData?.id,
              payload: buildMutualFundPayload(mfForm),
              isMutualFund: true,
            }
          : {
              mode: isEditing ? 'update' : 'create',
              transactionId: initialData?.id,
              payload: buildStockPayload(stockForm),
              isMutualFund: false,
            };
        storeBuyShortfall(apiShortfall, assetSubmit);
      } else {
        const impact = futureImpactFromApiError(err);
        if (impact) {
          setFutureImpact(impact);
          setError('');
        } else {
          setError(err.message || 'Save failed');
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const retryAssetSubmit = async (pending) => {
    if (pending.mode === 'update') {
      await updateTransaction(pending.transactionId, pending.payload);
    } else {
      await createTransaction(pending.payload);
    }
  };

  const handleAddMissingCashAndContinue = async () => {
    if (addAndContinueInFlight.current || !shortfall || !pendingAssetSubmit) return;
    addAndContinueInFlight.current = true;
    setAddAndContinueLoading(true);
    setError('');
    setPartialWarning('');

    const form = pendingAssetSubmit.isMutualFund ? mfForm : stockForm;
    const depositPayload = buildShortfallDepositPayload(
      shortfall,
      form,
      pendingAssetSubmit.isMutualFund,
      {
        sourceOfFunds: shortfallDeposit.source_of_funds,
        note: shortfallDeposit.note,
      }
    );

    try {
      await createCashDeposit(depositPayload);
    } catch (err) {
      setError(err.message || 'Cash deposit failed');
      addAndContinueInFlight.current = false;
      setAddAndContinueLoading(false);
      return;
    }

    try {
      await retryAssetSubmit(pendingAssetSubmit);
      onSuccess?.({
        kind: 'asset',
        message: 'Cash deposit added and purchase recorded.',
      });
      onClose();
    } catch (err) {
      const apiShortfall = shortfallFromApiError(err);
      setPartialWarning(PARTIAL_PURCHASE_WARNING);
      if (apiShortfall) {
        setError('Insufficient cash balance for purchase.');
        setShortfall(apiShortfall);
        setPendingAssetSubmit(pendingAssetSubmit);
      } else {
        const detail = err.detail || err.message;
        setError(detail ? String(detail) : 'Purchase could not be recorded.');
      }
    } finally {
      addAndContinueInFlight.current = false;
      setAddAndContinueLoading(false);
    }
  };

  const navStatus = initialData?.nav_verification_status;
  const navMessage = initialData?.nav_verification_message;

  const stockSellPreview =
    !isMutualFund && stockForm.type === 'SELL'
      ? {
          calculated: previewStockCalculatedProceeds(stockForm),
          withheld: previewTaxWithheld(
            previewStockCalculatedProceeds(stockForm),
            stockForm.actual_cash_received
          ),
          currency: stockForm.currency,
        }
      : null;

  const mfSellPreview =
    isMutualFund && mfForm.type === 'SELL'
      ? {
          calculated: previewMfCalculatedProceeds(mfForm),
          withheld: previewTaxWithheld(
            previewMfCalculatedProceeds(mfForm),
            mfForm.actual_cash_received
          ),
          currency: mfForm.currency,
        }
      : null;

  const submitLabel = submitting
    ? 'Saving...'
    : addAndContinueLoading
      ? 'Saving...'
      : isCash
      ? cashAction === 'deposit'
        ? 'Record deposit'
        : 'Record withdrawal'
      : 'Save';

  return (
    <div className="modal-overlay">
      <div className={`modal-content${isMutualFund ? ' modal-content--wide' : ''}`}>
        <h3>{isEditing ? 'Edit Transaction' : 'Add Transaction'}</h3>
        {partialWarning ? <div className="modal-warning">{partialWarning}</div> : null}
        {error && <div className="modal-error">{error}</div>}

        <form className="modal-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Record type</label>
            <select
              aria-label="record type"
              name="record_type"
              value={recordType}
              onChange={handleRecordTypeChange}
              disabled={isEditing}
            >
              <option value="CASH">Cash</option>
              <option value="STOCK">Stock</option>
              <option value="MUTUAL_FUND">Mutual Fund</option>
            </select>
          </div>

          {isCash ? (
            <>
              <p className="modal-form__hint">
                Cash entries can be edited from the Cash page.
              </p>
              <CashEntryFormFields
                form={cashForm}
                onFieldChange={handleCashFieldChange}
                cashAction={cashAction}
                onCashActionChange={setCashAction}
                showActionSelector
                activePortfolios={activePortfolios}
                requirePortfolioPick={requirePortfolioPick}
                shortfall={shortfall}
                idPrefix="txn-modal-cash"
              />
            </>
          ) : (
            <>
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

                  {mfForm.type === 'SELL' ? (
                    <div className="modal-sell-settlement">
                      {mfSellPreview?.calculated != null ? (
                        <p className="modal-sell-settlement__preview">
                          Calculated proceeds: {mfSellPreview.calculated.toFixed(2)}{' '}
                          {mfSellPreview.currency}
                        </p>
                      ) : null}
                      <div className="form-group">
                        <label>Actual cash received</label>
                        <input
                          type="number"
                          step="any"
                          name="actual_cash_received"
                          value={mfForm.actual_cash_received}
                          onChange={handleMfChange}
                        />
                        <p className="modal-form__hint">
                          Leave empty to use calculated proceeds.
                        </p>
                      </div>
                      {mfSellPreview?.withheld != null && mfSellPreview.withheld > 0 ? (
                        <p className="modal-sell-settlement__withheld">
                          Tax withheld / broker adjustment: {mfSellPreview.withheld.toFixed(2)}{' '}
                          {mfSellPreview.currency}
                        </p>
                      ) : null}
                      <div className="form-group">
                        <label>Settlement note / tax note</label>
                        <input
                          type="text"
                          name="settlement_note"
                          value={mfForm.settlement_note}
                          onChange={handleMfChange}
                        />
                      </div>
                    </div>
                  ) : null}

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
                      {stockForm.type === 'SELL' ? (
                        <div className="modal-sell-settlement">
                          {stockSellPreview?.calculated != null ? (
                            <p className="modal-sell-settlement__preview">
                              Calculated proceeds: {stockSellPreview.calculated.toFixed(2)}{' '}
                              {stockSellPreview.currency}
                            </p>
                          ) : null}
                          <div className="form-group">
                            <label>Actual cash received</label>
                            <input
                              type="number"
                              step="any"
                              name="actual_cash_received"
                              value={stockForm.actual_cash_received}
                              onChange={handleStockChange}
                            />
                            <p className="modal-form__hint">
                              Leave empty to use calculated proceeds.
                            </p>
                          </div>
                          {stockSellPreview?.withheld != null &&
                          stockSellPreview.withheld > 0 ? (
                            <p className="modal-sell-settlement__withheld">
                              Tax withheld / broker adjustment:{' '}
                              {stockSellPreview.withheld.toFixed(2)} {stockSellPreview.currency}
                            </p>
                          ) : null}
                          <div className="form-group">
                            <label>Settlement note / tax note</label>
                            <input
                              type="text"
                              name="settlement_note"
                              value={stockForm.settlement_note}
                              onChange={handleStockChange}
                            />
                          </div>
                        </div>
                      ) : null}
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

              {futureImpact && !isCash ? (
                <CashFutureImpactDisplay
                  impact={futureImpact}
                  intro={TRANSACTION_FUTURE_IMPACT_INTRO}
                  helperText={TRANSACTION_FUTURE_IMPACT_HELPER}
                />
              ) : null}

              {shortfall && !isCash ? (
                <>
                  <CashShortfallDisplay
                    shortfall={shortfall}
                    variant={isAssetBuy ? 'purchase' : undefined}
                  />
                  {showPurchaseShortfallAction ? (
                    <PurchaseShortfallAction
                      shortfall={shortfall}
                      sourceOfFunds={shortfallDeposit.source_of_funds}
                      note={shortfallDeposit.note}
                      onSourceOfFundsChange={(value) =>
                        setShortfallDeposit((prev) => ({ ...prev, source_of_funds: value }))
                      }
                      onNoteChange={(value) =>
                        setShortfallDeposit((prev) => ({ ...prev, note: value }))
                      }
                      onConfirm={handleAddMissingCashAndContinue}
                      loading={addAndContinueLoading}
                      disabled={busy}
                    />
                  ) : null}
                  <p className="modal-form__hint">
                    <Link to="/cash">Open Cash page</Link>
                  </p>
                </>
              ) : null}
            </>
          )}

          <div className="modal-actions">
            <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={busy}>
              {submitLabel}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
