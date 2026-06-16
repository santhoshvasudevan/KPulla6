import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import './Layout.css';
import { useAuth } from '../authContext';
import { usePortfolio } from '../portfolioContext';
import { Button, WarningBanner } from './ui';
import ThemeSelector from './ThemeSelector';

function Layout() {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const {
    selectorOptions,
    selectedPortfolioMode,
    selectedPortfolioId,
    selectedPortfolioName,
    selectedDisplayCurrency,
    settingsLoaded,
    setDisplayCurrency,
    setSelectedPortfolioMode,
    setSelectedPortfolioId,
    setSelectedPortfolioName,
    portfoliosError,
  } = usePortfolio();

  const selectedValue =
    selectedPortfolioMode === 'portfolio' && selectedPortfolioId != null
      ? `portfolio:${selectedPortfolioId}`
      : 'all';

  const onChange = (e) => {
    const v = e.target.value;
    if (v === 'all') {
      setSelectedPortfolioMode('all');
      setSelectedPortfolioId(null);
      setSelectedPortfolioName('All Portfolios');
      return;
    }
    if (v.startsWith('portfolio:')) {
      const id = Number(v.split(':')[1]);
      const opt = selectorOptions.find((o) => o.mode === 'portfolio' && Number(o.id) === id);
      setSelectedPortfolioMode('portfolio');
      setSelectedPortfolioId(id);
      setSelectedPortfolioName(opt?.name || selectedPortfolioName);
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
      <aside className="app-sidebar" aria-label="Application sidebar">
        <div className="app-sidebar__brand">
          <h1 className="app-sidebar__logo">Portfolio Insight</h1>
          <p className="app-sidebar__subtitle">Portfolio analytics</p>
        </div>

        <div className="app-sidebar__controls">
          <div className="app-sidebar__field">
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

          <div className="app-sidebar__field">
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

          {portfoliosError ? (
            <WarningBanner
              severity="warning"
              message={`Using All Portfolios (${portfoliosError})`}
              className="app-sidebar__notice"
            />
          ) : null}
        </div>

        <nav className="app-sidebar__nav" aria-label="Main navigation">
          <NavLink
            to="/"
            className={({ isActive }) =>
              `app-sidebar__nav-link${isActive ? ' app-sidebar__nav-link--active' : ''}`
            }
            end
          >
            Dashboard
          </NavLink>
          <NavLink
            to="/transactions"
            className={({ isActive }) =>
              `app-sidebar__nav-link${isActive ? ' app-sidebar__nav-link--active' : ''}`
            }
          >
            Transactions
          </NavLink>
          <NavLink
            to="/cash"
            className={({ isActive }) =>
              `app-sidebar__nav-link${isActive ? ' app-sidebar__nav-link--active' : ''}`
            }
          >
            Cash
          </NavLink>
          <NavLink
            to="/assets"
            className={({ isActive }) =>
              `app-sidebar__nav-link${isActive ? ' app-sidebar__nav-link--active' : ''}`
            }
          >
            Assets
          </NavLink>
          <NavLink
            to="/fixed-deposits"
            className={({ isActive }) =>
              `app-sidebar__nav-link${isActive ? ' app-sidebar__nav-link--active' : ''}`
            }
          >
            Fixed Deposits
          </NavLink>
          <NavLink
            to="/compare"
            className={({ isActive }) =>
              `app-sidebar__nav-link${isActive ? ' app-sidebar__nav-link--active' : ''}`
            }
          >
            Compare
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `app-sidebar__nav-link${isActive ? ' app-sidebar__nav-link--active' : ''}`
            }
          >
            Settings
          </NavLink>
        </nav>

        <p className="app-sidebar__footer-text">
          Valuations use cached prices and FX from the database.
        </p>
      </aside>

      <main className="app-main">
        <header className="app-header" aria-label="Application header">
          <div className="app-header__actions">
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
        <div className="app-main__inner">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default Layout;
