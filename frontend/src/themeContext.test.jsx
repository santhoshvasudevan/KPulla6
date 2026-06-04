import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { ThemeProvider, useTheme } from './themeContext';
import { THEME_PREFERENCE_KEY } from './theme/themeStorage';

function ThemeProbe() {
  const { themePreference, resolvedTheme, setThemePreference } = useTheme();
  return (
    <div>
      <span data-testid="preference">{themePreference}</span>
      <span data-testid="resolved">{resolvedTheme}</span>
      <button type="button" onClick={() => setThemePreference('dark')}>
        Set dark
      </button>
      <button type="button" onClick={() => setThemePreference('light')}>
        Set light
      </button>
      <button type="button" onClick={() => setThemePreference('system')}>
        Set system
      </button>
    </div>
  );
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    localStorage.removeItem(THEME_PREFERENCE_KEY);
    document.documentElement.dataset.theme = 'dark';
  });

  it('restores stored preference on mount', async () => {
    localStorage.setItem(THEME_PREFERENCE_KEY, 'light');
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );
    await waitFor(() => {
      expect(screen.getByTestId('preference').textContent).toBe('light');
      expect(screen.getByTestId('resolved').textContent).toBe('light');
      expect(document.documentElement.dataset.theme).toBe('light');
    });
  });

  it('stores dark and applies data-theme on selection', async () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Set dark' }));
    await waitFor(() => {
      expect(localStorage.getItem(THEME_PREFERENCE_KEY)).toBe('dark');
      expect(document.documentElement.dataset.theme).toBe('dark');
    });
  });

  it('stores light and applies data-theme on selection', async () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Set light' }));
    await waitFor(() => {
      expect(localStorage.getItem(THEME_PREFERENCE_KEY)).toBe('light');
      expect(document.documentElement.dataset.theme).toBe('light');
    });
  });

  it('stores system preference', async () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Set system' }));
    await waitFor(() => {
      expect(localStorage.getItem(THEME_PREFERENCE_KEY)).toBe('system');
      expect(screen.getByTestId('preference').textContent).toBe('system');
    });
  });
});
