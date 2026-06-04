import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  applyResolvedThemeToDocument,
  readStoredThemePreference,
  resolveTheme,
  writeStoredThemePreference,
} from './theme/themeStorage';

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [themePreference, setThemePreferenceState] = useState(readStoredThemePreference);
  const [resolvedTheme, setResolvedTheme] = useState(() => resolveTheme(readStoredThemePreference()));

  useEffect(() => {
    const resolved = resolveTheme(themePreference);
    setResolvedTheme(resolved);
    applyResolvedThemeToDocument(resolved);
  }, [themePreference]);

  useEffect(() => {
    if (themePreference !== 'system') {
      return undefined;
    }
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => {
      const resolved = resolveTheme('system');
      setResolvedTheme(resolved);
      applyResolvedThemeToDocument(resolved);
    };
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [themePreference]);

  const setThemePreference = useCallback((next) => {
    const normalized =
      next === 'light' || next === 'dark' || next === 'system' ? next : 'system';
    writeStoredThemePreference(normalized);
    setThemePreferenceState(normalized);
  }, []);

  const value = useMemo(
    () => ({
      themePreference,
      resolvedTheme,
      setThemePreference,
    }),
    [themePreference, resolvedTheme, setThemePreference]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return ctx;
}
