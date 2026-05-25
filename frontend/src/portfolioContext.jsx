import { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react';
import { fetchPortfolios, getSettings, updateSettings, invalidateDashboardSummaryCache } from './api';

const PortfolioContext = createContext(null);

export function PortfolioProvider({
  children,
  initialPortfolios = null,
  initialSelection = null,
  disableFetch = false,
}) {
  const [portfolios, setPortfolios] = useState(Array.isArray(initialPortfolios) ? initialPortfolios : []);
  const [portfoliosError, setPortfoliosError] = useState('');

  // Default selection = All Portfolios (virtual)
  const [selectedPortfolioMode, setSelectedPortfolioMode] = useState(initialSelection?.mode || 'all'); // 'all' | 'portfolio'
  const [selectedPortfolioId, setSelectedPortfolioId] = useState(initialSelection?.id ?? null);
  const [selectedPortfolioName, setSelectedPortfolioName] = useState(initialSelection?.name || 'All Portfolios');

  const [selectedDisplayCurrency, setSelectedDisplayCurrency] = useState('EUR');

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
      })
      .catch(() => {
        if (cancelled) return;
        setSelectedDisplayCurrency('EUR');
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

  const selectorOptions = useMemo(() => {
    const real = (portfolios || []).filter((p) => p && p.is_active);
    return [
      { mode: 'all', id: null, name: 'All Portfolios' },
      ...real.map((p) => ({ mode: 'portfolio', id: p.id, name: p.name })),
    ];
  }, [portfolios]);

  const apiQuery = useMemo(() => {
    if (selectedPortfolioMode === 'portfolio' && selectedPortfolioId != null) {
      return { portfolio_id: selectedPortfolioId, display_currency: selectedDisplayCurrency };
    }
    return { portfolio_scope: 'all', display_currency: selectedDisplayCurrency };
  }, [selectedPortfolioMode, selectedPortfolioId, selectedDisplayCurrency]);

  const value = useMemo(
    () => ({
      portfolios,
      portfoliosError,
      selectorOptions,
      selectedPortfolioMode,
      selectedPortfolioId,
      selectedPortfolioName,
      selectedDisplayCurrency,
      setDisplayCurrency,
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
      setDisplayCurrency,
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

