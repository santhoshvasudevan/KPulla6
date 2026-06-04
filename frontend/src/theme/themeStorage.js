export const THEME_PREFERENCE_KEY = 'kpulla6.themePreference';

/** @typedef {'light' | 'dark' | 'system'} ThemePreference */
/** @typedef {'light' | 'dark'} ResolvedTheme */

/** @type {ThemePreference[]} */
export const THEME_PREFERENCES = ['system', 'light', 'dark'];

/**
 * @param {string | null | undefined} value
 * @returns {ThemePreference}
 */
export function normalizeThemePreference(value) {
  if (value === 'light' || value === 'dark' || value === 'system') {
    return value;
  }
  return 'system';
}

/**
 * @returns {ThemePreference}
 */
export function readStoredThemePreference() {
  try {
    return normalizeThemePreference(localStorage.getItem(THEME_PREFERENCE_KEY));
  } catch {
    return 'system';
  }
}

/**
 * @param {ThemePreference} preference
 */
export function writeStoredThemePreference(preference) {
  try {
    localStorage.setItem(THEME_PREFERENCE_KEY, preference);
  } catch {
    // Private mode or blocked storage — preference applies for session only.
  }
}

/**
 * @returns {ResolvedTheme}
 */
export function getSystemResolvedTheme() {
  if (typeof window === 'undefined' || !window.matchMedia) {
    return 'dark';
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * @param {ThemePreference} preference
 * @returns {ResolvedTheme}
 */
export function resolveTheme(preference) {
  if (preference === 'light' || preference === 'dark') {
    return preference;
  }
  return getSystemResolvedTheme();
}

/**
 * @param {ResolvedTheme} resolved
 */
export function applyResolvedThemeToDocument(resolved) {
  if (typeof document === 'undefined') {
    return;
  }
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
}
