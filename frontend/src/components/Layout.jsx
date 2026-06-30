import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import './Layout.css';
import { useAuth } from '../authContext';
import { usePortfolio } from '../portfolioContext';
import { Button, WarningBanner } from './ui';
import ThemeSelector from './ThemeSelector';

const PRIMARY_NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/transactions', label: 'Transactions' },
  { to: '/cash', label: 'Cash' },
  { to: '/assets', label: 'Assets' },
  { to: '/fixed-deposits', label: 'Fixed Deposits' },
  { to: '/compare', label: 'Compare' },
  { to: '/settings', label: 'Settings' },
];

function Layout() {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const {
    portfolios,
    selectorOptions,
    selectedPortfolioMode,
    selectedPortfolioId,
    selectedPortfolioName,
    selectedDisplayCurrency,
    settingsLoaded,
    setDisplayCurrency,
    applyPortfolioViewSelection,
    portfoliosError,
  } = usePortfolio();

  const selectedValue =
    selectedPortfolioMode === 'portfolio' && selectedPortfolioId != null
      ? `portfolio:${selectedPortfolioId}`
      : 'all';

  const onChange = async (e) => {
    const v = e.target.value;
    if (v === 'all') {
      await applyPortfolioViewSelection({ mode: 'all' });
      return;
    }
    if (v.startsWith('portfolio:')) {
      const id = Number(v.split(':')[1]);
      const opt = selectorOptions.find((o) => o.mode === 'portfolio' && Number(o.id) === id);
      const portfolio = portfolios.find((p) => p.id === id);
      await applyPortfolioViewSelection({
        mode: 'portfolio',
        id,
        name: opt?.name || selectedPortfolioName,
        portfolio,
      });
    }
  };

  const onDisplayCurrencyChange = async (e) => {
    const next = e.target.value;
    try {
      await setDisplayCurrency(next);
    } catch (_) {
      // If settings update fails, keep selection unchanged.
    }
  };

  const onLogout = async () => {
    try {
      await logout();
    } finally {
      navigate('/login', { replace: true });
    }
  };

  const accountLabel = user?.email || user?.username || 'Account';

  return (
    <div className="app-shell">
      <header className="app-header" aria-label="Application header">
        <div className="app-header__brand">
          <div className="app-header__brand-mark" aria-hidden="true">
            K
          </div>
          <div>
            <h1 className="app-header__logo">KPulla6</h1>
            <p className="app-header__subtitle">Executive Portfolio OS</p>
            <p className="app-header__data-note" role="note">
              Cached prices, NAVs, benchmarks, and FX from the database
            </p>
          </div>
        </div>

        <nav className="app-sidebar__nav app-header__nav" aria-label="Main navigation">
          {PRIMARY_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `app-sidebar__nav-link${isActive ? ' app-sidebar__nav-link--active' : ''}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="app-header__actions">
          <div className="app-sidebar__field app-header__field">
            <label className="app-sidebar__label" htmlFor="sidebar-portfolio-view">
              Portfolio View
            </label>
            <select
              id="sidebar-portfolio-view"
              aria-label="portfolio-view"
              className="app-sidebar__select"
              value={selectedValue}
              onChange={onChange}
            >
              {selectorOptions.map((o) => (
                <option
                  key={o.mode === 'all' ? 'all' : `p-${o.id}`}
                  value={o.mode === 'all' ? 'all' : `portfolio:${o.id}`}
                >
                  {o.name}
                </option>
              ))}
            </select>
          </div>

          <div className="app-sidebar__field app-header__field app-header__field--currency">
            <label className="app-sidebar__label" htmlFor="sidebar-display-currency">
              Display Currency
            </label>
            <select
              id="sidebar-display-currency"
              aria-label="display-currency"
              className="app-sidebar__select"
              value={(selectedDisplayCurrency || 'EUR').toUpperCase()}
              onChange={onDisplayCurrencyChange}
              disabled={!settingsLoaded}
              aria-busy={!settingsLoaded}
            >
              {!settingsLoaded ? (
                <option value="EUR">Loading…</option>
              ) : (
                ['EUR', 'USD', 'INR', 'GBP', 'CHF'].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))
              )}
            </select>
          </div>

          <ThemeSelector />
          <div className="app-header__account">
            <span className="app-header__user" title={accountLabel}>
              {accountLabel}
            </span>
            <Button variant="secondary" className="app-header__logout" onClick={onLogout}>
              Log out
            </Button>
          </div>
        </div>
      </header>

      {portfoliosError ? (
        <WarningBanner
          severity="warning"
          message={`Using All Portfolios (${portfoliosError})`}
          className="app-shell__notice"
        />
      ) : null}

      <main className="app-main">
        <div className="app-main__inner" id="main-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default Layout;
