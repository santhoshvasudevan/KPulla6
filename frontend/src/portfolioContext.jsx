import { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react';
import { fetchPortfolios, getSettings, updateSettings, invalidateDashboardSummaryCache } from './api';
import { displayCurrencyForPortfolio } from './utils/displayCurrency';

export { DISPLAY_CURRENCY_CHOICES } from './utils/displayCurrency';

const PortfolioContext = createContext(null);

export function PortfolioProvider({
  children,
  initialPortfolios = null,
  initialSelection = null,
  initialDisplayCurrency = 'EUR',
  disableFetch = false,
}) {
  const [portfolios, setPortfolios] = useState(Array.isArray(initialPortfolios) ? initialPortfolios : []);
  const [portfoliosError, setPortfoliosError] = useState('');

  // Default selection = All Portfolios (virtual)
  const [selectedPortfolioMode, setSelectedPortfolioMode] = useState(initialSelection?.mode || 'all'); // 'all' | 'portfolio'
  const [selectedPortfolioId, setSelectedPortfolioId] = useState(initialSelection?.id ?? null);
  const [selectedPortfolioName, setSelectedPortfolioName] = useState(initialSelection?.name || 'All Portfolios');

  const [settingsLoaded, setSettingsLoaded] = useState(disableFetch);
  const [selectedDisplayCurrency, setSelectedDisplayCurrency] = useState(
    disableFetch ? String(initialDisplayCurrency || 'EUR').toUpperCase() : null
  );

  useEffect(() => {
    if (disableFetch) return;
    let cancelled = false;
    fetchPortfolios()
      .then((rows) => {
        if (cancelled) return;
        setPortfolios(Array.isArray(rows) ? rows : []);
        setPortfoliosError('');
      })
      .catch((e) => {
        if (cancelled) return;
        setPortfolios([]);
        setPortfoliosError(e?.message || 'Failed to load portfolios');
      });
    return () => {
      cancelled = true;
    };
  }, [disableFetch]);

  useEffect(() => {
    if (disableFetch) return;
    let cancelled = false;
    getSettings()
      .then((s) => {
        if (cancelled) return;
        const c = String(s?.display_currency || 'EUR').toUpperCase();
        setSelectedDisplayCurrency(c || 'EUR');
        setSettingsLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setSelectedDisplayCurrency('EUR');
        setSettingsLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [disableFetch]);

  const setDisplayCurrency = useCallback(async (nextCurrency) => {
    const c = String(nextCurrency || 'EUR').toUpperCase();
    await updateSettings({ display_currency: c });
    invalidateDashboardSummaryCache();
    setSelectedDisplayCurrency(c);
  }, []);

  const reloadPortfolios = useCallback(async () => {
    try {
      const rows = await fetchPortfolios();
      const list = Array.isArray(rows) ? rows : [];
      setPortfolios(list);
      setPortfoliosError('');

      if (selectedPortfolioMode === 'portfolio' && selectedPortfolioId != null) {
        const match = list.find((p) => p.id === selectedPortfolioId && p.is_active);
        if (match) {
          setSelectedPortfolioName(match.name);
        } else {
          setSelectedPortfolioMode('all');
          setSelectedPortfolioId(null);
          setSelectedPortfolioName('All Portfolios');
        }
      }
      return list;
    } catch (e) {
      setPortfolios([]);
      setPortfoliosError(e?.message || 'Failed to load portfolios');
      throw e;
    }
  }, [selectedPortfolioMode, selectedPortfolioId]);

  const selectPortfolio = useCallback(
    async (id, name, options = {}) => {
      setSelectedPortfolioMode('portfolio');
      setSelectedPortfolioId(id);
      setSelectedPortfolioName(name || '');
      const portfolio =
        options.portfolio || portfolios.find((p) => p.id === id) || null;
      const nextCurrency = displayCurrencyForPortfolio(portfolio);
      if (
        nextCurrency &&
        settingsLoaded &&
        nextCurrency !== selectedDisplayCurrency
      ) {
        await setDisplayCurrency(nextCurrency);
      }
    },
    [portfolios, settingsLoaded, selectedDisplayCurrency, setDisplayCurrency]
  );

  const selectAllPortfolios = useCallback(() => {
    setSelectedPortfolioMode('all');
    setSelectedPortfolioId(null);
    setSelectedPortfolioName('All Portfolios');
  }, []);

  const applyPortfolioViewSelection = useCallback(
    async (selection) => {
      if (selection.mode === 'all') {
        selectAllPortfolios();
        return;
      }
      await selectPortfolio(selection.id, selection.name, {
        portfolio: selection.portfolio,
      });
    },
    [selectAllPortfolios, selectPortfolio]
  );

  const selectorOptions = useMemo(() => {
    const real = (portfolios || []).filter((p) => p && p.is_active);
    return [
      { mode: 'all', id: null, name: 'All Portfolios' },
      ...real.map((p) => ({ mode: 'portfolio', id: p.id, name: p.name })),
    ];
  }, [portfolios]);

  const apiQuery = useMemo(() => {
    if (!settingsLoaded || !selectedDisplayCurrency) return null;
    if (selectedPortfolioMode === 'portfolio' && selectedPortfolioId != null) {
      return { portfolio_id: selectedPortfolioId, display_currency: selectedDisplayCurrency };
    }
    return { portfolio_scope: 'all', display_currency: selectedDisplayCurrency };
  }, [settingsLoaded, selectedPortfolioMode, selectedPortfolioId, selectedDisplayCurrency]);

  const value = useMemo(
    () => ({
      portfolios,
      portfoliosError,
      selectorOptions,
      selectedPortfolioMode,
      selectedPortfolioId,
      selectedPortfolioName,
      selectedDisplayCurrency,
      settingsLoaded,
      setDisplayCurrency,
      reloadPortfolios,
      selectPortfolio,
      selectAllPortfolios,
      applyPortfolioViewSelection,
      setSelectedPortfolioMode,
      setSelectedPortfolioId,
      setSelectedPortfolioName,
      apiQuery,
    }),
    [
      portfolios,
      portfoliosError,
      selectorOptions,
      selectedPortfolioMode,
      selectedPortfolioId,
      selectedPortfolioName,
      selectedDisplayCurrency,
      settingsLoaded,
      setDisplayCurrency,
      reloadPortfolios,
      selectPortfolio,
      selectAllPortfolios,
      applyPortfolioViewSelection,
      apiQuery,
    ]
  );

  return <PortfolioContext.Provider value={value}>{children}</PortfolioContext.Provider>;
}

export function usePortfolio() {
  const ctx = useContext(PortfolioContext);
  if (!ctx) throw new Error('usePortfolio must be used within PortfolioProvider');
  return ctx;
}
