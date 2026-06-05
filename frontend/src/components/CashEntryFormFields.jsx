import { SUPPORTED_CASH_CURRENCIES } from '../constants/cashCurrencies';
import CashShortfallDisplay from './CashShortfallDisplay';

export function emptyCashForm(portfolioId = '') {
  return {
    portfolio_id: portfolioId,
    date: new Date().toISOString().split('T')[0],
    currency: 'EUR',
    amount: '',
    source_of_funds: '',
    note: '',
  };
}

/**
 * Shared cash deposit/withdrawal fields (native currency; no balance math in React).
 */
export default function CashEntryFormFields({
  form,
  onFieldChange,
  cashAction = 'deposit',
  onCashActionChange,
  showActionSelector = true,
  activePortfolios = [],
  requirePortfolioPick = false,
  shortfall = null,
  idPrefix = 'cash-form',
}) {
  const singlePortfolio =
    !requirePortfolioPick && activePortfolios.length === 1 ? activePortfolios[0] : null;

  return (
    <>
      {showActionSelector && onCashActionChange ? (
        <div className="form-group">
          <label htmlFor={`${idPrefix}-action`}>Action</label>
          <select
            id={`${idPrefix}-action`}
            aria-label="cash action"
            value={cashAction}
            onChange={(e) => onCashActionChange(e.target.value)}
          >
            <option value="deposit">Deposit</option>
            <option value="withdrawal">Withdrawal</option>
          </select>
        </div>
      ) : null}

      {requirePortfolioPick || activePortfolios.length > 1 ? (
        <div className="form-group">
          <label htmlFor={`${idPrefix}-portfolio`}>Portfolio</label>
          <select
            id={`${idPrefix}-portfolio`}
            aria-label="cash portfolio"
            value={form.portfolio_id}
            onChange={(e) => onFieldChange('portfolio_id', e.target.value)}
          >
            {requirePortfolioPick ? (
              <option value="">Select portfolio…</option>
            ) : null}
            {activePortfolios.map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      ) : singlePortfolio ? (
        <div className="form-group">
          <label>Portfolio</label>
          <p className="modal-form__readonly-value">{singlePortfolio.name}</p>
        </div>
      ) : null}

      <div className="form-group">
        <label htmlFor={`${idPrefix}-date`}>Date</label>
        <input
          id={`${idPrefix}-date`}
          type="date"
          value={form.date}
          onChange={(e) => onFieldChange('date', e.target.value)}
          required
        />
      </div>

      <div className="form-group">
        <label htmlFor={`${idPrefix}-currency`}>Currency</label>
        <select
          id={`${idPrefix}-currency`}
          aria-label="cash currency"
          value={form.currency}
          onChange={(e) => onFieldChange('currency', e.target.value)}
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
        <label htmlFor={`${idPrefix}-amount`}>Amount</label>
        <input
          id={`${idPrefix}-amount`}
          type="number"
          min="0"
          step="0.01"
          value={form.amount}
          onChange={(e) => onFieldChange('amount', e.target.value)}
          required
        />
      </div>

      <div className="form-group">
        <label htmlFor={`${idPrefix}-source`}>Source of funds</label>
        <input
          id={`${idPrefix}-source`}
          type="text"
          value={form.source_of_funds}
          onChange={(e) => onFieldChange('source_of_funds', e.target.value)}
          placeholder="Optional"
        />
      </div>

      <div className="form-group">
        <label htmlFor={`${idPrefix}-note`}>Note</label>
        <textarea
          id={`${idPrefix}-note`}
          rows={2}
          value={form.note}
          onChange={(e) => onFieldChange('note', e.target.value)}
          placeholder="Optional"
        />
      </div>

      <CashShortfallDisplay shortfall={shortfall} />
    </>
  );
}
