import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Register from './Register';

const mockRegister = vi.fn();
const mockNavigate = vi.fn();

vi.mock('../../authContext', () => ({
  useAuth: () => ({
    register: mockRegister,
  }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('./AuthShell', () => ({
  AuthShell: ({ children, title }) => (
    <div>
      <h1>{title}</h1>
      {children}
    </div>
  ),
  GoogleSignInButton: () => <button type="button">Google</button>,
}));

function fillRegisterForm() {
  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'newuser' } });
  fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'new@example.com' } });
  fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'StrongPass123!' } });
  fireEvent.change(screen.getByLabelText(/confirm password/i), {
    target: { value: 'StrongPass123!' },
  });
}

describe('Register page', () => {
  beforeEach(() => {
    mockRegister.mockReset();
    mockNavigate.mockReset();
  });

  it('renders registration form fields and actions', () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    expect(screen.getByLabelText(/^username$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^register$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /google/i })).toBeInTheDocument();
  });

  it('shows backend validation error message', async () => {
    mockRegister.mockRejectedValueOnce(
      new Error('username: A user with that username already exists.')
    );
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    fillRegisterForm();
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'taken' } });
    fireEvent.click(screen.getByRole('button', { name: /^register$/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/username: A user with that username already exists/i)
      ).toBeInTheDocument();
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('navigates home after successful registration', async () => {
    mockRegister.mockResolvedValueOnce({ id: 2, username: 'newuser' });
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    fillRegisterForm();
    fireEvent.click(screen.getByRole('button', { name: /^register$/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard', { replace: true });
    });
  });
});
