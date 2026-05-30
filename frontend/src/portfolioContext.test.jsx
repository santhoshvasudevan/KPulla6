import { render, waitFor } from '@testing-library/react';
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
