import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  THEME_PREFERENCE_KEY,
  normalizeThemePreference,
  readStoredThemePreference,
  writeStoredThemePreference,
  resolveTheme,
  applyResolvedThemeToDocument,
} from './themeStorage';

function clearThemeStorage() {
  localStorage.removeItem(THEME_PREFERENCE_KEY);
}

describe('themeStorage', () => {
  beforeEach(() => {
    clearThemeStorage();
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.style.colorScheme = '';
  });

  it('defaults to system when localStorage is empty', () => {
    expect(readStoredThemePreference()).toBe('system');
    expect(normalizeThemePreference(null)).toBe('system');
  });

  it('persists dark preference', () => {
    writeStoredThemePreference('dark');
    expect(localStorage.getItem(THEME_PREFERENCE_KEY)).toBe('dark');
    expect(readStoredThemePreference()).toBe('dark');
  });

  it('persists light preference', () => {
    writeStoredThemePreference('light');
    expect(readStoredThemePreference()).toBe('light');
  });

  it('resolveTheme maps preference to light or dark', () => {
    expect(resolveTheme('light')).toBe('light');
    expect(resolveTheme('dark')).toBe('dark');
  });

  it('resolveTheme uses OS preference for system mode', () => {
    vi.spyOn(window, 'matchMedia').mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    expect(resolveTheme('system')).toBe('dark');

    window.matchMedia.mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    expect(resolveTheme('system')).toBe('light');
  });

  it('applyResolvedThemeToDocument sets data-theme and color-scheme', () => {
    applyResolvedThemeToDocument('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');

    applyResolvedThemeToDocument('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });
});
