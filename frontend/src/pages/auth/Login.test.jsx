import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Login from './Login';

const mockLogin = vi.fn();
const mockNavigate = vi.fn();

vi.mock('../../authContext', () => ({
  useAuth: () => ({
    login: mockLogin,
  }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>
  );
}

function fillLoginForm() {
  fireEvent.change(screen.getByLabelText(/username or email/i), {
    target: { value: 'demo@example.com' },
  });
  fireEvent.change(screen.getByLabelText(/^password$/i), {
    target: { value: 'StrongPass123!' },
  });
}

describe('Login page', () => {
  beforeEach(() => {
    mockLogin.mockReset();
    mockNavigate.mockReset();
  });

  it('renders the public login form and auth links without the authenticated app shell', () => {
    renderLogin();

    expect(screen.getByText('KPulla6')).toBeInTheDocument();
    expect(screen.getByText('Executive Portfolio OS')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.getByLabelText(/username or email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^sign in$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /forgot password/i })).toHaveAttribute(
      'href',
      '/forgot-password'
    );
    expect(screen.getAllByRole('link', { name: /register first/i }).length).toBeGreaterThan(0);
    expect(screen.queryByLabelText('Main navigation')).not.toBeInTheDocument();
  });

  it('submits credentials and navigates home on success', async () => {
    mockLogin.mockResolvedValueOnce({ id: 1, email: 'demo@example.com' });
    renderLogin();

    fillLoginForm();
    fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('demo@example.com', 'StrongPass123!');
      expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
    });
  });

  it('shows login errors and stays on the page', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Invalid username or password.'));
    renderLogin();

    fillLoginForm();
    fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }));

    expect(await screen.findByText('Invalid username or password.')).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
