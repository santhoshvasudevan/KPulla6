import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import Layout from './Layout';
import { PortfolioProvider, usePortfolio } from '../portfolioContext';
import { AuthProvider } from '../authContext';
import { ThemeProvider } from '../themeContext';
import * as api from '../api';

vi.mock('../api', () => ({
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
  ensureCsrfCookie: vi.fn(),
  fetchCurrentUser: vi.fn().mockResolvedValue({ id: 1, username: 'demo', email: 'demo@example.com' }),
  logout: vi.fn(),
}));

function renderLayout(ui) {
  return render(
    <ThemeProvider>
      <AuthProvider>
        <PortfolioProvider>{ui}</PortfolioProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

describe('Layout component', () => {
  it('renders navigation links and outlet', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    renderLayout(
      <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<div data-testid="child">Child Content</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
    );

    expect(screen.getByLabelText('display-currency')).toBeDisabled();
    await waitFor(() => {
      expect(screen.getByLabelText('display-currency')).not.toBeDisabled();
    });

    expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/transactions/i)).toBeInTheDocument();
    expect(screen.getByText(/assets/i)).toBeInTheDocument();
    expect(screen.getByText(/^compare$/i)).toBeInTheDocument();
    expect(screen.getByText(/settings/i)).toBeInTheDocument();
    expect(screen.getByText(/portfolio view/i)).toBeInTheDocument();
    expect(screen.getByLabelText('portfolio-view')).toBeInTheDocument();
    expect(screen.getByText(/display currency/i)).toBeInTheDocument();
    expect(screen.getByLabelText('display-currency')).toBeInTheDocument();
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('shows account and logout in the top header', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    renderLayout(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<div data-testid="child">Child Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('display-currency')).not.toBeDisabled();
    });

    expect(screen.getByLabelText('Application header')).toBeInTheDocument();
    expect(screen.getByText('demo@example.com')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /log out/i })).toHaveLength(1);
  });

  it('renders theme selector in the application header', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    renderLayout(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<div data-testid="child">Child</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Theme preference')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Theme preference')).toHaveValue('system');
  });

  it('renders portfolio and currency controls before navigation links', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    renderLayout(
      <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<div data-testid="child">Child Content</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('display-currency')).not.toBeDisabled();
    });

    const portfolioView = screen.getByLabelText('portfolio-view');
    const displayCurrency = screen.getByLabelText('display-currency');
    const dashboardLink = screen.getByRole('link', { name: /dashboard/i });

    expect(
      portfolioView.compareDocumentPosition(dashboardLink) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(
      displayCurrency.compareDocumentPosition(dashboardLink) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  });

  it('updates display currency via sidebar and persists through context', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.updateSettings.mockResolvedValue({ display_currency: 'INR' });

    renderLayout(
      <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<div data-testid="child">Child</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
    );

    const currencySelect = await screen.findByLabelText('display-currency');
    fireEvent.change(currencySelect, { target: { value: 'INR' } });

    await waitFor(() => {
      expect(api.updateSettings).toHaveBeenCalledWith({ display_currency: 'INR' });
      expect(currencySelect).toHaveValue('INR');
    });
  });

  it('shows renamed portfolio in selector after reloadPortfolios', async () => {
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchPortfolios.mockResolvedValueOnce([
      { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
      { id: 2, name: 'Old Name', is_default: false, is_active: true, base_currency: 'EUR' },
    ]);

    function TestHarness() {
      const { reloadPortfolios } = usePortfolio();
      return (
        <>
          <button type="button" onClick={() => reloadPortfolios()}>
            Reload
          </button>
          <Layout />
        </>
      );
    }

    api.fetchPortfolios.mockResolvedValueOnce([
      { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
      { id: 2, name: 'Renamed Portfolio', is_default: false, is_active: true, base_currency: 'EUR' },
    ]);

    renderLayout(
      <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="/" element={<TestHarness />}>
              <Route index element={<div data-testid="child">Child</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('portfolio-view')).toBeInTheDocument();
    });

    expect(screen.getByRole('option', { name: 'Old Name' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Reload' }));

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Renamed Portfolio' })).toBeInTheDocument();
    });
    expect(screen.queryByRole('option', { name: 'Old Name' })).not.toBeInTheDocument();
  });
});
