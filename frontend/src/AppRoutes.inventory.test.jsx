import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockAuth = vi.hoisted(() => ({
  user: null,
  loading: false,
  isAuthenticated: false,
  login: vi.fn(),
  logout: vi.fn(),
  register: vi.fn(),
  refreshUser: vi.fn(),
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    BrowserRouter: ({ children }) => children,
  };
});

vi.mock('./themeContext', () => ({
  ThemeProvider: ({ children }) => children,
}));

vi.mock('./authContext', () => ({
  AuthProvider: ({ children }) => children,
  useAuth: () => mockAuth,
}));

vi.mock('./portfolioContext', () => ({
  PortfolioProvider: ({ children }) => children,
}));

vi.mock('./api', () => ({
  setUnauthorizedHandler: vi.fn(),
}));

vi.mock('./components/Layout', async () => {
  const { Outlet } = await vi.importActual('react-router-dom');
  return {
    default: () => (
      <div>
        <div data-testid="app-shell">App shell</div>
        <Outlet />
      </div>
    ),
  };
});

vi.mock('./pages/Dashboard', () => ({ default: () => <h1>Dashboard route</h1> }));
vi.mock('./pages/Transactions', () => ({ default: () => <h1>Transactions route</h1> }));
vi.mock('./pages/Cash', () => ({ default: () => <h1>Cash route</h1> }));
vi.mock('./pages/Assets', () => ({ default: () => <h1>Assets route</h1> }));
vi.mock('./pages/AssetDetail', () => ({ default: () => <h1>Asset detail route</h1> }));
vi.mock('./pages/FixedDeposits', () => ({ default: () => <h1>Fixed Deposits route</h1> }));
vi.mock('./pages/Compare', () => ({ default: () => <h1>Compare route</h1> }));
vi.mock('./pages/Settings', () => ({ default: () => <h1>Settings route</h1> }));
vi.mock('./pages/auth/Login', () => ({ default: () => <h1>Login route</h1> }));
vi.mock('./pages/auth/Register', () => ({ default: () => <h1>Register route</h1> }));
vi.mock('./pages/auth/ForgotPassword', () => ({ default: () => <h1>Forgot Password route</h1> }));

import App from './App';

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>
  );
}

describe('App route inventory', () => {
  beforeEach(() => {
    mockAuth.loading = false;
    mockAuth.user = null;
    mockAuth.isAuthenticated = false;
  });

  it.each([
    ['/login', 'Login route'],
    ['/register', 'Register route'],
    ['/forgot-password', 'Forgot Password route'],
  ])('renders public auth route %s without the authenticated app shell', async (path, heading) => {
    renderAt(path);

    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument();
    expect(screen.queryByTestId('app-shell')).not.toBeInTheDocument();
  });

  it.each([
    ['/', 'Dashboard route'],
    ['/dashboard', 'Dashboard route'],
    ['/transactions', 'Transactions route'],
    ['/cash', 'Cash route'],
    ['/assets', 'Assets route'],
    ['/assets/AAPL', 'Asset detail route'],
    ['/fixed-deposits', 'Fixed Deposits route'],
    ['/compare', 'Compare route'],
    ['/settings', 'Settings route'],
    ['/unknown-route', 'Dashboard route'],
  ])('renders protected route or redirect %s inside the app shell', async (path, heading) => {
    mockAuth.user = { id: 1, username: 'demo', email: 'demo@example.com' };
    mockAuth.isAuthenticated = true;

    renderAt(path);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    });
    expect(screen.getByTestId('app-shell')).toBeInTheDocument();
  });

  it('redirects protected routes to login when unauthenticated', async () => {
    renderAt('/transactions');

    expect(await screen.findByRole('heading', { name: 'Login route' })).toBeInTheDocument();
    expect(screen.queryByTestId('app-shell')).not.toBeInTheDocument();
  });
});
