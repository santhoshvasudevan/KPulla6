import { useEffect, useState } from 'react';
import { getSettings, updateSettings } from '../api';
import { usePortfolio } from '../portfolioContext';
import {
  PageHeader,
  SectionCard,
  Button,
  LoadingState,
  ErrorState,
  WarningBanner,
} from '../components/ui';
import './Settings.css';

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
      <PageHeader title="Settings" />

      <SectionCard title="Display & tax">
        <form onSubmit={handleSubmit} className="settings-form">
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
              Sidebar selector uses the same setting (current: {selectedDisplayCurrency}).
            </p>
          </div>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Saving…' : 'Save Settings'}
          </Button>
        </form>
        {status ? (
          <WarningBanner severity="success" message={status} className="settings-banner" />
        ) : null}
        {error && taxRate ? (
          <WarningBanner severity="error" message={error} className="settings-banner" />
        ) : null}
      </SectionCard>
    </div>
  );
}
