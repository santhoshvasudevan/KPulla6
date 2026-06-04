import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GOOGLE_LOGIN_PATH, GoogleSignInButton } from './AuthShell';

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
});
