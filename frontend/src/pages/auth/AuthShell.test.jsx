import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthShell, GOOGLE_LOGIN_PATH, GoogleSignInButton, resolveGoogleLoginUrl } from './AuthShell';

describe('AuthShell', () => {
  it('renders KPulla6 brand identity and panel title', () => {
    render(
      <MemoryRouter>
        <AuthShell title="Sign in" subtitle="Secure portfolio access">
          <p>Form body</p>
        </AuthShell>
      </MemoryRouter>
    );

    expect(screen.getByText('KPulla6')).toBeInTheDocument();
    expect(screen.getByText('Executive Portfolio OS')).toBeInTheDocument();
    expect(screen.getByText('Secure portfolio access')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.getByText('Form body')).toBeInTheDocument();
  });
});

describe('GoogleSignInButton', () => {
  beforeEach(() => {
    vi.stubGlobal('location', { assign: vi.fn(), href: '' });
  });

  it('uses the canonical django-allauth Google login path', () => {
    expect(GOOGLE_LOGIN_PATH).toBe('/accounts/google/login/?process=login');
  });

  it('starts Google OAuth via location.assign on the login path', () => {
    render(<GoogleSignInButton />);
    fireEvent.click(screen.getByRole('button', { name: /sign in with google/i }));
    expect(window.location.assign).toHaveBeenCalledWith(GOOGLE_LOGIN_PATH);
  });

  it('starts Google OAuth on localhost when the app is opened at 127.0.0.1', () => {
    expect(
      resolveGoogleLoginUrl({ hostname: '127.0.0.1', port: '5173' })
    ).toBe(`http://localhost:5173${GOOGLE_LOGIN_PATH}`);
    expect(resolveGoogleLoginUrl({ hostname: '::1', port: '5173' })).toBe(
      `http://localhost:5173${GOOGLE_LOGIN_PATH}`
    );
    expect(resolveGoogleLoginUrl({ hostname: 'localhost', port: '5173' })).toBe(
      GOOGLE_LOGIN_PATH
    );
  });
});
