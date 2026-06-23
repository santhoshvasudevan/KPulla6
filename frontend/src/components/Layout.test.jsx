import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
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

    const primaryNav = screen.getByLabelText('Main navigation');
    expect(within(primaryNav).getByText(/dashboard/i)).toBeInTheDocument();
    expect(within(primaryNav).getByText(/transactions/i)).toBeInTheDocument();
    expect(within(primaryNav).getByText(/^cash$/i)).toBeInTheDocument();
    expect(within(primaryNav).getByText(/assets/i)).toBeInTheDocument();
    expect(within(primaryNav).getByText(/fixed deposits/i)).toBeInTheDocument();
    expect(within(primaryNav).getByText(/^compare$/i)).toBeInTheDocument();
    expect(within(primaryNav).getByText(/settings/i)).toBeInTheDocument();
    expect(screen.getByText(/portfolio view/i)).toBeInTheDocument();
    expect(screen.getByLabelText('portfolio-view')).toBeInTheDocument();
    expect(screen.getByText(/display currency/i)).toBeInTheDocument();
    expect(screen.getByLabelText('display-currency')).toBeInTheDocument();
    expect(screen.queryByLabelText('Secondary navigation')).not.toBeInTheDocument();
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('centers main content globally without a context sidebar', async () => {
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

    const main = document.querySelector('.app-main');
    const inner = document.getElementById('main-content');
    expect(main).toBeInTheDocument();
    expect(inner).toHaveClass('app-main__inner');
    expect(screen.queryByLabelText('Secondary navigation')).not.toBeInTheDocument();
  });

  it('does not render secondary context navigation on non-dashboard routes', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    renderLayout(
      <MemoryRouter initialEntries={['/cash']}>
        <Routes>
          <Route path="/cash" element={<Layout />}>
            <Route index element={<div data-testid="child">Cash child</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('display-currency')).not.toBeDisabled();
    });
    expect(screen.queryByLabelText('Secondary navigation')).not.toBeInTheDocument();
    expect(screen.getByTestId('child')).toBeInTheDocument();
    expect(document.getElementById('main-content')).toHaveClass('app-main__inner');
  });

  it('shows compact cached-data note in the application header', async () => {
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
      expect(
        screen.getByText(/cached prices, navs, benchmarks, and fx from the database/i)
      ).toBeInTheDocument();
    });
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

  it('renders primary navigation before portfolio and currency controls in the top shell', async () => {
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
      dashboardLink.compareDocumentPosition(portfolioView) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(
      dashboardLink.compareDocumentPosition(displayCurrency) & Node.DOCUMENT_POSITION_FOLLOWING
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

  it('renders seven primary navigation links in the authenticated shell', async () => {
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
      expect(screen.getByLabelText('display-currency')).not.toBeDisabled();
    });

    const primaryNav = screen.getByLabelText('Main navigation');
    expect(within(primaryNav).getAllByRole('link')).toHaveLength(7);
  });

  it('highlights Cash nav link on /cash route', async () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    renderLayout(
      <MemoryRouter initialEntries={['/cash']}>
        <Routes>
          <Route path="/cash" element={<Layout />}>
            <Route index element={<div data-testid="child">Cash child</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('display-currency')).not.toBeDisabled();
    });

    const cashLink = screen.getByRole('link', { name: /^cash$/i });
    expect(cashLink).toHaveClass('app-sidebar__nav-link--active');
  });
});
