import { useMemo, useState } from 'react';
import { updatePortfolio } from '../api';
import { usePortfolio } from '../portfolioContext';
import {
  buildCashAwareEnablePayload,
  CASH_AWARE_ALL_SCOPE_NOTE,
  CASH_AWARE_ENABLE_CONFIRM,
  CASH_AWARE_OFF_MESSAGE,
  CASH_AWARE_ON_MESSAGE,
} from '../utils/portfolioCashAware';
import { Button, WarningBanner } from './ui';
import './CashAwarePortfolioStatus.css';

/**
 * Cash-aware status and optional enable action for the sidebar-selected portfolio.
 */
export default function CashAwarePortfolioStatus({ className = '' }) {
  const { selectedPortfolioMode, selectedPortfolioId, portfolios, reloadPortfolios } =
    usePortfolio();
  const [enabling, setEnabling] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const selectedPortfolio = useMemo(() => {
    if (selectedPortfolioMode !== 'portfolio' || selectedPortfolioId == null) return null;
    return (
      (portfolios || []).find((p) => p && p.is_active && p.id === selectedPortfolioId) ?? null
    );
  }, [selectedPortfolioMode, selectedPortfolioId, portfolios]);

  const rootClass = ['cash-aware-status', className].filter(Boolean).join(' ');

  if (selectedPortfolioMode === 'all') {
    return (
      <div className={rootClass}>
        <WarningBanner severity="info" message={CASH_AWARE_ALL_SCOPE_NOTE} />
      </div>
    );
  }

  if (!selectedPortfolio) return null;

  const isOn = selectedPortfolio.cash_aware_enabled === true;

  const handleEnable = async () => {
    if (!window.confirm(CASH_AWARE_ENABLE_CONFIRM)) return;
    setError('');
    setSuccess('');
    setEnabling(true);
    try {
      await updatePortfolio(
        selectedPortfolio.id,
        buildCashAwareEnablePayload(selectedPortfolio)
      );
      await reloadPortfolios();
      setSuccess('Cash-aware mode enabled for this portfolio.');
    } catch (err) {
      setError(err.message || 'Could not enable cash-aware mode.');
    } finally {
      setEnabling(false);
    }
  };

  return (
    <div className={rootClass}>
      {success ? (
        <WarningBanner severity="success" message={success} className="cash-aware-status__banner" />
      ) : null}
      {error ? (
        <WarningBanner severity="error" message={error} className="cash-aware-status__banner" />
      ) : null}
      <div className="cash-aware-status__panel">
        <p className="cash-aware-status__message">
          {isOn ? CASH_AWARE_ON_MESSAGE : CASH_AWARE_OFF_MESSAGE}
        </p>
        {!isOn ? (
          <Button
            type="button"
            variant="primary"
            disabled={enabling}
            onClick={handleEnable}
          >
            {enabling ? 'Enabling…' : 'Enable cash-aware mode'}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
