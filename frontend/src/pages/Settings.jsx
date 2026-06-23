import { useEffect, useState } from 'react';
import { getSettings, updateSettings } from '../api';
import { usePortfolio } from '../portfolioContext';
import {
  PageHeader,
  AppCard,
  Button,
  LoadingState,
  ErrorState,
  WarningBanner,
} from '../components/ui';
import PortfolioManagement from '../components/PortfolioManagement';
import BankAccountManagement from '../components/BankAccountManagement';
import './Settings.css';

const SETTINGS_SECTION_NAV = [
  { href: '#settings-display', label: 'Display' },
  { href: '#settings-portfolios', label: 'Portfolios' },
  { href: '#settings-bank-accounts', label: 'Bank Accounts' },
  { href: '#settings-data-sync', label: 'Data Sync' },
];

export default function Settings() {
  const { selectedDisplayCurrency, setDisplayCurrency } = usePortfolio();
  const [taxRate, setTaxRate] = useState('');
  const [displayCurrency, setDisplayCurrencyLocal] = useState('EUR');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getSettings()
      .then((data) => {
        setTaxRate(String(data.tax_rate_percentage));
        setDisplayCurrencyLocal(String(data.display_currency || 'EUR').toUpperCase());
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus('');
    setError('');
    setSubmitting(true);
    try {
      await updateSettings({
        tax_rate_percentage: parseFloat(taxRate),
        display_currency: displayCurrency,
      });
      await setDisplayCurrency(displayCurrency);
      setStatus('Settings saved.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingState message="Loading settings…" />;
  if (error && !taxRate) {
    return <ErrorState title="Error loading settings" message={error} />;
  }

  return (
    <div className="settings-page">
      <PageHeader
        title="Settings"
        subtitle="Workspace preferences, portfolios, bank accounts, and cached market data guidance"
        eyebrow="Executive Portfolio OS"
      />

      <nav className="settings-section-nav" aria-label="Settings section navigation">
        {SETTINGS_SECTION_NAV.map((item) => (
          <a key={item.href} className="settings-section-nav__link" href={item.href}>
            {item.label}
          </a>
        ))}
      </nav>

      <div className="settings-page__sections">
        <div id="settings-display">
          <AppCard
            className="settings-page__card"
            title="Display & tax"
            subtitle="Default display currency and tax rate for portfolio views"
          >
            <form onSubmit={handleSubmit} className="settings-form">
              <div className="settings-form__grid">
                <div className="form-group">
                  <label htmlFor="tax-rate">Tax Rate (%)</label>
                  <input
                    id="tax-rate"
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={taxRate}
                    onChange={(e) => setTaxRate(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="display-currency">Display Currency</label>
                  <select
                    id="display-currency"
                    value={displayCurrency}
                    onChange={(e) => setDisplayCurrencyLocal(e.target.value)}
                  >
                    {['EUR', 'USD', 'INR', 'GBP', 'CHF'].map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <p className="settings-hint">
                    Header selector uses the same setting (current: {selectedDisplayCurrency}).
                  </p>
                </div>
              </div>
              <div className="settings-form__actions">
                <Button type="submit" variant="primary" disabled={submitting}>
                  {submitting ? 'Saving…' : 'Save Settings'}
                </Button>
              </div>
            </form>
            {status ? (
              <WarningBanner severity="success" message={status} className="settings-banner" />
            ) : null}
            {error && taxRate ? (
              <WarningBanner severity="error" message={error} className="settings-banner" />
            ) : null}
          </AppCard>
        </div>

        <div id="settings-portfolios">
          <AppCard
            className="settings-page__card"
            title="Portfolios"
            subtitle="Create, rename, and manage cash-aware portfolio modes"
          >
            <PortfolioManagement />
          </AppCard>
        </div>

        <div id="settings-bank-accounts">
          <AppCard
            className="settings-page__card"
            title="Bank accounts"
            subtitle="Link accounts to fixed deposits and manage cash ledger movements"
          >
            <p className="settings-hint settings-page__bank-intro">
              Link bank accounts to fixed deposits. Account numbers are stored and displayed as
              entered.
            </p>
            <BankAccountManagement />
          </AppCard>
        </div>

        <div id="settings-data-sync">
          <AppCard className="settings-page__card" title="Data & sync">
            <p className="settings-sync-note">
              Market data is cached in the database. Dashboard, holdings, summary, and performance
              reads use cached prices, FX rates, benchmark levels, and mutual fund NAVs only — no live
              external calls on page load.
            </p>
            <p className="settings-sync-note">
              To refresh cached data, run <code>make refresh</code> (or{' '}
              <code>make sync-market-data</code>) on the backend. Full sync includes stock prices,
              benchmark indices, FX rates, and mutual fund NAVs. Stock-only refresh:{' '}
              <code>POST /api/v1/prices/refresh</code>. Mutual fund NAV only:{' '}
              <code>POST /api/v1/nav/refresh</code>. Combined sync:{' '}
              <code>POST /api/v1/portfolio/force-sync</code>.
            </p>
          </AppCard>
        </div>
      </div>
    </div>
  );
}
