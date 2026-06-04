import { useTheme } from '../themeContext';
import './ThemeSelector.css';

const OPTIONS = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

export default function ThemeSelector() {
  const { themePreference, setThemePreference } = useTheme();

  return (
    <div className="theme-selector">
      <label className="theme-selector__label" htmlFor="app-theme-preference">
        Theme
      </label>
      <select
        id="app-theme-preference"
        className="theme-selector__select"
        value={themePreference}
        onChange={(e) => setThemePreference(e.target.value)}
        aria-label="Theme preference"
      >
        {OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
