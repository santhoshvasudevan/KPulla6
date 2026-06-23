import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ForgotPassword from './ForgotPassword';
import { requestPasswordReset } from '../../api';

vi.mock('../../api', () => ({
  requestPasswordReset: vi.fn(),
}));

function renderForgotPassword() {
  return render(
    <MemoryRouter>
      <ForgotPassword />
    </MemoryRouter>
  );
}

describe('ForgotPassword page', () => {
  beforeEach(() => {
    requestPasswordReset.mockReset();
  });

  it('renders the password reset form and back-to-login link without the authenticated app shell', () => {
    renderForgotPassword();

    expect(screen.getByRole('heading', { name: 'Reset password' })).toBeInTheDocument();
    expect(screen.getByText('KPulla6')).toBeInTheDocument();
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to sign in/i })).toHaveAttribute(
      'href',
      '/login'
    );
    expect(screen.queryByLabelText('Main navigation')).not.toBeInTheDocument();
  });

  it('submits the email and shows the backend success detail', async () => {
    requestPasswordReset.mockResolvedValueOnce({
      detail: 'Password reset instructions were sent if that account exists.',
    });
    renderForgotPassword();

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: 'demo@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() => {
      expect(requestPasswordReset).toHaveBeenCalledWith('demo@example.com');
      expect(
        screen.getByText('Password reset instructions were sent if that account exists.')
      ).toBeInTheDocument();
    });
  });

  it('shows password reset API errors', async () => {
    requestPasswordReset.mockRejectedValueOnce(new Error('Email service unavailable.'));
    renderForgotPassword();

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: 'demo@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(await screen.findByText('Email service unavailable.')).toBeInTheDocument();
  });
});
