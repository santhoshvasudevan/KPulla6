import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Settings from './Settings';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', () => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  fetchPortfolios: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

function renderSettings() {
  return render(
    <PortfolioProvider disableFetch initialPortfolios={[]}>
      <Settings />
    </PortfolioProvider>
  );
}

describe('Settings Page', () => {
  it('shows loading state initially', () => {
    api.getSettings.mockReturnValueOnce(new Promise(() => {}));
    renderSettings();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders the tax rate form after loading', async () => {
    api.getSettings.mockResolvedValueOnce({ tax_rate_percentage: 15.0 });
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText(/tax rate/i)).toBeInTheDocument();
      expect(screen.getByDisplayValue('15')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    });
  });

  it('shows error on API failure', async () => {
    api.getSettings.mockRejectedValueOnce(new Error('Failed'));
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });
});
