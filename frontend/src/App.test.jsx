import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    BrowserRouter: ({ children }) => children,
  };
});

import App from './App';

const mockAuth = {
  user: null,
  loading: false,
  isAuthenticated: false,
  login: vi.fn(),
  logout: vi.fn(),
  register: vi.fn(),
  refreshUser: vi.fn(),
};

vi.mock('./authContext', () => ({
  AuthProvider: ({ children }) => children,
  useAuth: () => mockAuth,
}));

vi.mock('./api', () => ({
  fetchPortfolios: vi.fn().mockResolvedValue([]),
  getSettings: vi.fn().mockResolvedValue({ display_currency: 'EUR', tax_rate_percentage: 26.375 }),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
  fetchDashboardSummary: vi.fn().mockResolvedValue({
    total_invested: 0,
    current_value: 0,
    realized_pl: 0,
    unrealized_pl: 0,
    total_pl: 0,
    xirr: null,
    display_currency: 'EUR',
    fx_status: 'ok',
  }),
  fetchPortfolioPerformance: vi.fn().mockResolvedValue([]),
  fetchBenchmarkIndices: vi.fn().mockResolvedValue([]),
  getPortfolioMetricSheet: vi.fn().mockResolvedValue({
    metrics: {
      return: { cumulative_return: null, cagr: null, xirr: null, xirr_scope: 'full_scope', twror: null },
      risk: { volatility_annualized: null, downside_deviation: null, sharpe_ratio: null, sortino_ratio: null },
      drawdown: { max_drawdown: null, longest_drawdown_days: null, calmar_ratio: null },
      periods: { best_day: null, worst_day: null, win_rate: null, average_daily_return: null },
    },
    warnings: [],
  }),
  setUnauthorizedHandler: vi.fn(),
  ensureCsrfCookie: vi.fn(),
}));

describe('App auth routing', () => {
  beforeEach(() => {
    localStorage.removeItem('kpulla6.themePreference');
    document.documentElement.dataset.theme = 'dark';
    mockAuth.user = null;
    mockAuth.loading = false;
    mockAuth.isAuthenticated = false;
    mockAuth.logout.mockReset();
  });

  it('shows landing page for unauthenticated root', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );
    expect(
      await screen.findByRole('heading', {
        name: /wealth is easier to build when it is clearly understood/i,
      })
    ).toBeTruthy();
    expect(screen.getByRole('link', { name: /^login$/i })).toHaveAttribute('href', '/login');
  });

  it('shows login page for unauthenticated /login', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByLabelText(/username or email/i)).toBeTruthy();
    expect(screen.getByLabelText(/^password$/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /sign in with google/i })).toBeTruthy();
    expect(screen.getByText(/forgot password/i)).toBeTruthy();
    expect(screen.getAllByText(/register first/i).length).toBeGreaterThan(0);
  });

  it('authenticated user sees dashboard at /dashboard', async () => {
    mockAuth.user = { id: 1, username: 'demo', email: 'demo@example.com' };
    mockAuth.isAuthenticated = true;
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByText('Dashboard')).toBeTruthy();
    expect(screen.getByText('Transactions')).toBeTruthy();
  });

  it('authenticated user visiting / is redirected to dashboard', async () => {
    mockAuth.user = { id: 1, username: 'demo', email: 'demo@example.com' };
    mockAuth.isAuthenticated = true;
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByText('Dashboard')).toBeTruthy();
    expect(screen.getByText('Transactions')).toBeTruthy();
  });

  it('protected route redirects to login when unauthenticated', async () => {
    render(
      <MemoryRouter initialEntries={['/transactions']}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByLabelText(/username or email/i)).toBeTruthy();
  });

  it('logout returns user to the landing page', async () => {
    mockAuth.user = { id: 1, username: 'demo', email: 'demo@example.com' };
    mockAuth.isAuthenticated = true;
    mockAuth.logout.mockImplementation(async () => {
      mockAuth.user = null;
      mockAuth.isAuthenticated = false;
    });
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>
    );
    await screen.findByLabelText('Theme preference');
    const logoutBtn = screen.getByRole('button', { name: /log out/i });
    fireEvent.click(logoutBtn);
    await waitFor(() => {
      expect(mockAuth.logout).toHaveBeenCalled();
    });
    expect(
      await screen.findByRole('heading', {
        name: /wealth is easier to build when it is clearly understood/i,
      })
    ).toBeTruthy();
  });
});
