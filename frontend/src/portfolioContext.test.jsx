import { render, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PortfolioProvider, usePortfolio } from './portfolioContext';
import * as api from './api';

vi.mock('./api', () => ({
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

function ApiQueryProbe() {
  const { apiQuery, settingsLoaded, selectedDisplayCurrency } = usePortfolio();
  return (
    <div>
      <span data-testid="settings-loaded">{String(settingsLoaded)}</span>
      <span data-testid="display-currency">{selectedDisplayCurrency ?? 'null'}</span>
      <span data-testid="api-query">{apiQuery ? JSON.stringify(apiQuery) : 'null'}</span>
    </div>
  );
}

function SelectPortfolioProbe() {
  const { selectPortfolio } = usePortfolio();
  return (
    <button
      type="button"
      onClick={() =>
        selectPortfolio(2, 'IndianInvestments', {
          portfolio: { id: 2, name: 'IndianInvestments', base_currency: 'INR' },
        })
      }
    >
      Select INR portfolio
    </button>
  );
}

describe('PortfolioProvider settings readiness', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchPortfolios.mockResolvedValue([]);
  });

  it('keeps apiQuery null until settings load', async () => {
    let resolveSettings;
    api.getSettings.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSettings = () => resolve({ display_currency: 'INR' });
      })
    );

    const { getByTestId } = render(
      <PortfolioProvider>
        <ApiQueryProbe />
      </PortfolioProvider>
    );

    expect(getByTestId('settings-loaded')).toHaveTextContent('false');
    expect(getByTestId('display-currency')).toHaveTextContent('null');
    expect(getByTestId('api-query')).toHaveTextContent('null');

    resolveSettings();
    await waitFor(() => {
      expect(getByTestId('settings-loaded')).toHaveTextContent('true');
      expect(getByTestId('display-currency')).toHaveTextContent('INR');
      expect(getByTestId('api-query')).toHaveTextContent(
        JSON.stringify({ portfolio_scope: 'all', display_currency: 'INR' })
      );
    });
  });

  it('exposes apiQuery immediately when disableFetch is set', () => {
    const { getByTestId } = render(
      <PortfolioProvider disableFetch initialDisplayCurrency="USD">
        <ApiQueryProbe />
      </PortfolioProvider>
    );

    expect(getByTestId('settings-loaded')).toHaveTextContent('true');
    expect(getByTestId('display-currency')).toHaveTextContent('USD');
    expect(getByTestId('api-query')).toHaveTextContent(
      JSON.stringify({ portfolio_scope: 'all', display_currency: 'USD' })
    );
  });
});

describe('PortfolioProvider display currency sync', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchPortfolios.mockResolvedValue([
      { id: 2, name: 'IndianInvestments', is_active: true, base_currency: 'INR' },
    ]);
    api.getSettings.mockResolvedValue({ display_currency: 'EUR' });
    api.updateSettings.mockResolvedValue({ display_currency: 'INR' });
  });

  it('syncs display currency when selecting a portfolio with supported base currency', async () => {
    const { getByRole, getByTestId } = render(
      <PortfolioProvider>
        <SelectPortfolioProbe />
        <ApiQueryProbe />
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(getByTestId('settings-loaded')).toHaveTextContent('true');
    });

    fireEvent.click(getByRole('button', { name: 'Select INR portfolio' }));

    await waitFor(() => {
      expect(api.updateSettings).toHaveBeenCalledWith({ display_currency: 'INR' });
      expect(getByTestId('display-currency')).toHaveTextContent('INR');
    });
  });
});
