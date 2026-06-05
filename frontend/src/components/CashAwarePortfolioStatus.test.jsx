import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CashAwarePortfolioStatus from './CashAwarePortfolioStatus';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';
import {
  CASH_AWARE_ALL_SCOPE_NOTE,
  CASH_AWARE_OFF_MESSAGE,
  CASH_AWARE_ON_MESSAGE,
} from '../utils/portfolioCashAware';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    updatePortfolio: vi.fn(),
    fetchPortfolios: vi.fn(),
  };
});

const legacyPortfolio = {
  id: 5,
  name: 'Default Portfolio',
  description: null,
  base_currency: 'USD',
  is_default: true,
  is_active: true,
  cash_aware_enabled: false,
};

const cashAwarePortfolio = {
  ...legacyPortfolio,
  id: 1,
  cash_aware_enabled: true,
};

function renderStatus({ initialSelection, initialPortfolios }) {
  return render(
    <PortfolioProvider
      disableFetch
      initialPortfolios={initialPortfolios}
      initialSelection={initialSelection}
    >
      <CashAwarePortfolioStatus />
    </PortfolioProvider>
  );
}

describe('CashAwarePortfolioStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
  });

  it('shows per-portfolio note in All Portfolios scope', () => {
    renderStatus({
      initialPortfolios: [legacyPortfolio],
      initialSelection: { mode: 'all', name: 'All Portfolios' },
    });
    expect(screen.getByText(CASH_AWARE_ALL_SCOPE_NOTE)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /enable cash-aware/i })).not.toBeInTheDocument();
  });

  it('shows off status and enable button for legacy portfolio', () => {
    renderStatus({
      initialPortfolios: [legacyPortfolio],
      initialSelection: { mode: 'portfolio', id: 5, name: 'Default Portfolio' },
    });
    expect(screen.getByText(CASH_AWARE_OFF_MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /enable cash-aware mode/i })).toBeInTheDocument();
  });

  it('shows on status without enable button when cash-aware', () => {
    renderStatus({
      initialPortfolios: [cashAwarePortfolio],
      initialSelection: { mode: 'portfolio', id: 1, name: 'Default Portfolio' },
    });
    expect(screen.getByText(CASH_AWARE_ON_MESSAGE)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /enable cash-aware/i })).not.toBeInTheDocument();
  });

  it('calls updatePortfolio with cash_aware_enabled true on confirm', async () => {
    api.updatePortfolio.mockResolvedValueOnce({ ...legacyPortfolio, cash_aware_enabled: true });
    api.fetchPortfolios.mockResolvedValueOnce([
      { ...legacyPortfolio, cash_aware_enabled: true },
    ]);
    renderStatus({
      initialPortfolios: [legacyPortfolio],
      initialSelection: { mode: 'portfolio', id: 5, name: 'Default Portfolio' },
    });
    fireEvent.click(screen.getByRole('button', { name: /enable cash-aware mode/i }));

    await waitFor(() => {
      expect(api.updatePortfolio).toHaveBeenCalledWith(5, {
        name: 'Default Portfolio',
        description: null,
        base_currency: 'USD',
        is_active: true,
        cash_aware_enabled: true,
      });
    });
  });

  it('shows success after enable and reload', async () => {
    api.updatePortfolio.mockResolvedValueOnce({ ...legacyPortfolio, cash_aware_enabled: true });
    api.fetchPortfolios.mockResolvedValueOnce([
      { ...legacyPortfolio, cash_aware_enabled: true },
    ]);
    renderStatus({
      initialPortfolios: [legacyPortfolio],
      initialSelection: { mode: 'portfolio', id: 5, name: 'Default Portfolio' },
    });
    fireEvent.click(screen.getByRole('button', { name: /enable cash-aware mode/i }));

    await waitFor(() => {
      expect(screen.getByText(/cash-aware mode enabled/i)).toBeInTheDocument();
    });
    expect(api.fetchPortfolios).toHaveBeenCalled();
  });

  it('does not call API when confirm is cancelled', async () => {
    window.confirm = vi.fn(() => false);
    renderStatus({
      initialPortfolios: [legacyPortfolio],
      initialSelection: { mode: 'portfolio', id: 5, name: 'Default Portfolio' },
    });
    fireEvent.click(screen.getByRole('button', { name: /enable cash-aware mode/i }));
    expect(api.updatePortfolio).not.toHaveBeenCalled();
  });
});
