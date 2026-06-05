import { Link } from 'react-router-dom';
import { Button, CurrencyValue } from './ui';
import './CsvImportCashPreviewModal.css';

/**
 * Cash-5 — user-confirmed CSV import deposits (backend preview payload only).
 */
export default function CsvImportCashPreviewModal({
  isOpen,
  preview,
  confirming = false,
  onConfirm,
  onCancel,
}) {
  if (!isOpen || !preview) return null;

  const totals = preview.summary?.total_shortfall_by_currency || [];
  const deposits = preview.proposed_deposits || [];

  return (
    <div className="modal-overlay">
      <div className="modal-content csv-import-cash-preview">
        <h3>This import requires additional cash</h3>
        <p className="csv-import-cash-preview__lead">
          Cash-aware portfolios need same-currency cash before purchases. No automatic FX
          conversion is applied.
        </p>

        {totals.length > 0 ? (
          <div className="csv-import-cash-preview__totals">
            <h4>Total shortfall by currency</h4>
            <ul>
              {totals.map((row) => (
                <li key={row.currency}>
                  <CurrencyValue value={row.amount} currency={row.currency} tone="loss" />
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {deposits.length > 0 ? (
          <div className="csv-import-cash-preview__deposits">
            <h4>Proposed cash deposits</h4>
            <table className="csv-import-cash-preview__table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Portfolio</th>
                  <th>Currency</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {deposits.map((dep, idx) => (
                  <tr key={`${dep.portfolio_id}-${dep.date}-${dep.currency}-${idx}`}>
                    <td>{dep.date}</td>
                    <td>{dep.portfolio_name || dep.portfolio_id}</td>
                    <td>{dep.currency}</td>
                    <td>
                      <CurrencyValue value={dep.amount} currency={dep.currency} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {preview.shortfalls?.length > 0 ? (
          <details className="csv-import-cash-preview__shortfalls">
            <summary>Shortfall details ({preview.shortfalls.length})</summary>
            <ul>
              {preview.shortfalls.map((sf, idx) => (
                <li key={`${sf.reason}-${sf.date}-${idx}`}>
                  {sf.reason} — {sf.date}: need{' '}
                  <CurrencyValue value={sf.shortfall} currency={sf.currency} /> (
                  available{' '}
                  <CurrencyValue value={sf.available_before} currency={sf.currency} />)
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        {confirming ? (
          <p className="csv-import-cash-preview__status" role="status">
            Adding required cash deposits and importing rows…
          </p>
        ) : null}

        <p className="csv-import-cash-preview__hint">
          <Link to="/cash">Open Cash page</Link> to review balances after import.
        </p>

        <div className="csv-import-cash-preview__actions">
          <Button type="button" variant="secondary" onClick={onCancel} disabled={confirming}>
            Cancel import
          </Button>
          <Button type="button" variant="primary" onClick={onConfirm} disabled={confirming}>
            Add required cash deposits and import all rows
          </Button>
        </div>
      </div>
    </div>
  );
}
