import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Settings from './Settings';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', () => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  fetchPortfolios: vi.fn(),
  createPortfolio: vi.fn(),
  updatePortfolio: vi.fn(),
  deletePortfolio: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

const defaultPortfolio = {
  id: 1,
  name: 'Default Portfolio',
  description: null,
  base_currency: 'EUR',
  is_default: true,
  is_active: true,
  cash_aware_enabled: false,
};

function renderSettings(portfolioProps = {}) {
  const {
    initialPortfolios = [defaultPortfolio],
    disableFetch = true,
    ...rest
  } = portfolioProps;
  return render(
    <PortfolioProvider
      disableFetch
      initialPortfolios={initialPortfolios}
      {...rest}
    >
      <Settings />
    </PortfolioProvider>
  );
}

describe('Settings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
  });

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
      expect(screen.getByRole('button', { name: /save settings/i })).toBeInTheDocument();
    });
  });

  it('shows data and sync explainer', async () => {
    api.getSettings.mockResolvedValueOnce({ tax_rate_percentage: 15.0, display_currency: 'EUR' });
    renderSettings();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Data & sync' })).toBeInTheDocument();
      expect(screen.getAllByText(/mutual fund NAVs/i).length).toBeGreaterThan(0);
    });
  });

  it('shows error on API failure', async () => {
    api.getSettings.mockRejectedValueOnce(new Error('Failed'));
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });

  it('creates portfolio and shows it after reload', async () => {
    api.getSettings.mockResolvedValueOnce({ tax_rate_percentage: 15.0, display_currency: 'EUR' });
    api.createPortfolio.mockResolvedValueOnce({
      id: 2,
      name: 'Growth',
      base_currency: 'EUR',
      is_default: false,
      is_active: true,
    });
    api.fetchPortfolios.mockResolvedValueOnce([
      defaultPortfolio,
      { id: 2, name: 'Growth', base_currency: 'EUR', is_default: false, is_active: true },
    ]);

    renderSettings();

    await waitFor(() => {
      expect(document.getElementById('portfolio-create-name')).toBeInTheDocument();
    });

    fireEvent.change(document.getElementById('portfolio-create-name'), {
      target: { value: 'Growth' },
    });
    fireEvent.click(screen.getByRole('button', { name: /create portfolio/i }));

    await waitFor(() => {
      expect(api.createPortfolio).toHaveBeenCalledWith({
        name: 'Growth',
        base_currency: 'EUR',
      });
      expect(api.fetchPortfolios).toHaveBeenCalled();
      expect(screen.getByText('Growth')).toBeInTheDocument();
    });
  });

  it('renames portfolio via updatePortfolio', async () => {
    api.getSettings.mockResolvedValueOnce({ tax_rate_percentage: 15.0, display_currency: 'EUR' });
    api.updatePortfolio.mockResolvedValueOnce({});
    api.fetchPortfolios.mockResolvedValueOnce([
      { ...defaultPortfolio, name: 'Renamed Default' },
    ]);

    renderSettings();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
    fireEvent.change(document.getElementById('portfolio-edit-name'), {
      target: { value: 'Renamed Default' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(api.updatePortfolio).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ name: 'Renamed Default' })
      );
      expect(api.fetchPortfolios).toHaveBeenCalled();
    });
  });

  it('enables cash-aware mode from portfolio table', async () => {
    api.getSettings.mockResolvedValueOnce({ tax_rate_percentage: 15.0, display_currency: 'EUR' });
    api.updatePortfolio.mockResolvedValueOnce({ ...defaultPortfolio, cash_aware_enabled: true });
    api.fetchPortfolios.mockResolvedValueOnce([
      { ...defaultPortfolio, cash_aware_enabled: true },
    ]);

    renderSettings();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /enable cash-aware/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /enable cash-aware/i }));

    await waitFor(() => {
      expect(api.updatePortfolio).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ cash_aware_enabled: true })
      );
      expect(screen.getByText(/cash-aware mode enabled/i)).toBeInTheDocument();
    });
  });

  it('does not show deactivate for default portfolio', async () => {
    api.getSettings.mockResolvedValueOnce({ tax_rate_percentage: 15.0, display_currency: 'EUR' });
    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('Default Portfolio')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /deactivate/i })).not.toBeInTheDocument();
  });

  it('shows backend error on duplicate portfolio name', async () => {
    api.getSettings.mockResolvedValueOnce({ tax_rate_percentage: 15.0, display_currency: 'EUR' });
    api.createPortfolio.mockRejectedValueOnce(new Error('A portfolio with this name already exists'));

    renderSettings();

    await waitFor(() => {
      expect(document.getElementById('portfolio-create-name')).toBeInTheDocument();
    });

    fireEvent.change(document.getElementById('portfolio-create-name'), {
      target: { value: 'Duplicate' },
    });
    fireEvent.click(screen.getByRole('button', { name: /create portfolio/i }));

    await waitFor(() => {
      expect(screen.getByText(/already exists/i)).toBeInTheDocument();
    });
  });

  it('disables create when max active portfolios reached', async () => {
    api.getSettings.mockResolvedValueOnce({ tax_rate_percentage: 15.0, display_currency: 'EUR' });
    const five = Array.from({ length: 5 }, (_, i) => ({
      id: i + 1,
      name: `P${i + 1}`,
      base_currency: 'EUR',
      is_default: i === 0,
      is_active: true,
    }));

    renderSettings({ initialPortfolios: five });

    await waitFor(() => {
      expect(screen.getByText(/maximum of 5 active portfolios/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /create portfolio/i })).toBeDisabled();
  });
});
