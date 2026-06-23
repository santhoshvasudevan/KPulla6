import { useEffect, useMemo, useRef, useState } from 'react';
import { Filter, X, ChevronDown, Search } from 'lucide-react';
import { Button } from './ui';
import './TransactionFilterBar.css';

const DATE_MODES = [
  { value: 'any', label: 'Any time' },
  { value: 'before', label: 'Earlier than' },
  { value: 'after', label: 'Later than' },
  { value: 'between', label: 'Between' },
];

function SymbolMultiSelect({ options, selected, onChange }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const handleClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase();
    if (!q) return options;
    return options.filter((s) => s.toUpperCase().includes(q));
  }, [options, search]);

  const toggle = (symbol) => {
    if (selected.includes(symbol)) {
      onChange(selected.filter((s) => s !== symbol));
    } else {
      onChange([...selected, symbol]);
    }
  };

  const buttonLabel =
    selected.length === 0
      ? 'All symbols'
      : selected.length === 1
        ? selected[0]
        : `${selected.length} symbols`;

  return (
    <div className="txn-filter__symbol" ref={containerRef}>
      <button
        type="button"
        className="txn-filter__symbol-toggle"
        aria-label="Filter by symbol"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span>{buttonLabel}</span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      {open ? (
        <div className="txn-filter__symbol-panel" role="listbox" aria-label="Symbol options">
          <div className="txn-filter__symbol-search">
            <Search size={14} aria-hidden="true" />
            <input
              type="text"
              autoFocus
              placeholder="Search symbols…"
              aria-label="Search symbols"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <ul className="txn-filter__symbol-list">
            {filtered.length === 0 ? (
              <li className="txn-filter__symbol-empty">No symbols</li>
            ) : (
              filtered.map((symbol) => (
                <li key={symbol}>
                  <label className="txn-filter__symbol-option">
                    <input
                      type="checkbox"
                      checked={selected.includes(symbol)}
                      onChange={() => toggle(symbol)}
                    />
                    <span>{symbol}</span>
                  </label>
                </li>
              ))
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export default function TransactionFilterBar({
  portfolios = [],
  symbolOptions = [],
  filterPortfolioId,
  onPortfolioChange,
  symbolFilter = [],
  onSymbolFilterChange,
  dateMode,
  onDateModeChange,
  dateValue,
  onDateValueChange,
  dateFrom,
  onDateFromChange,
  dateTo,
  onDateToChange,
  dateRangeInvalid = false,
  hasActiveFilters = false,
  onClearFilters,
  embedded = false,
}) {
  const portfolioName = useMemo(() => {
    const match = portfolios.find((p) => String(p.id) === String(filterPortfolioId));
    return match ? match.name : '';
  }, [portfolios, filterPortfolioId]);

  const dateChipLabel = useMemo(() => {
    if (dateMode === 'before' && dateValue) return `Earlier than ${dateValue}`;
    if (dateMode === 'after' && dateValue) return `Later than ${dateValue}`;
    if (dateMode === 'between' && (dateFrom || dateTo)) {
      return `Between ${dateFrom || '…'} and ${dateTo || '…'}`;
    }
    return '';
  }, [dateMode, dateValue, dateFrom, dateTo]);

  return (
    <section
      className={`txn-filter${embedded ? ' txn-filter--embedded' : ''}`}
      aria-label="Transaction filters"
    >
      <div className="txn-filter__row">
        {embedded ? null : (
          <div className="txn-filter__heading">
            <Filter size={16} aria-hidden="true" />
            <span>Filters</span>
          </div>
        )}

        <div className="txn-filter__control">
          <label className="txn-filter__label" htmlFor="txn-filter-portfolio">
            Portfolio
          </label>
          <select
            id="txn-filter-portfolio"
            className="txn-filter__select"
            aria-label="Filter by portfolio"
            value={filterPortfolioId}
            onChange={(e) => onPortfolioChange(e.target.value)}
          >
            <option value="">All portfolios</option>
            {portfolios.map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div className="txn-filter__control">
          <span className="txn-filter__label">Symbol</span>
          <SymbolMultiSelect
            options={symbolOptions}
            selected={symbolFilter}
            onChange={onSymbolFilterChange}
          />
        </div>

        <div className="txn-filter__control">
          <label className="txn-filter__label" htmlFor="txn-filter-date-mode">
            Date
          </label>
          <div className="txn-filter__date-group">
            <select
              id="txn-filter-date-mode"
              className="txn-filter__select"
              aria-label="Date filter mode"
              value={dateMode}
              onChange={(e) => onDateModeChange(e.target.value)}
            >
              {DATE_MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
            {dateMode === 'before' || dateMode === 'after' ? (
              <input
                type="date"
                className="txn-filter__date-input"
                aria-label="Date value"
                value={dateValue}
                onChange={(e) => onDateValueChange(e.target.value)}
              />
            ) : null}
            {dateMode === 'between' ? (
              <div className="txn-filter__date-range">
                <input
                  type="date"
                  className="txn-filter__date-input"
                  aria-label="Date from"
                  value={dateFrom}
                  onChange={(e) => onDateFromChange(e.target.value)}
                />
                <span className="txn-filter__date-sep">–</span>
                <input
                  type="date"
                  className="txn-filter__date-input"
                  aria-label="Date to"
                  value={dateTo}
                  onChange={(e) => onDateToChange(e.target.value)}
                />
              </div>
            ) : null}
          </div>
        </div>

        {hasActiveFilters ? (
          <Button
            type="button"
            variant="ghost"
            className="txn-filter__clear"
            onClick={onClearFilters}
          >
            Clear filters
          </Button>
        ) : null}
      </div>

      {dateRangeInvalid ? (
        <p className="txn-filter__error" role="alert">
          “From” date must be on or before “To” date.
        </p>
      ) : null}

      {hasActiveFilters ? (
        <div className="txn-filter__chips" aria-label="Active filters">
          {portfolioName ? (
            <span className="txn-filter__chip">
              Portfolio: {portfolioName}
              <button
                type="button"
                aria-label="Remove portfolio filter"
                onClick={() => onPortfolioChange('')}
              >
                <X size={12} aria-hidden="true" />
              </button>
            </span>
          ) : null}
          {symbolFilter.map((symbol) => (
            <span className="txn-filter__chip" key={symbol}>
              {symbol}
              <button
                type="button"
                aria-label={`Remove symbol ${symbol}`}
                onClick={() => onSymbolFilterChange(symbolFilter.filter((s) => s !== symbol))}
              >
                <X size={12} aria-hidden="true" />
              </button>
            </span>
          ))}
          {dateChipLabel ? (
            <span className="txn-filter__chip">
              {dateChipLabel}
              <button
                type="button"
                aria-label="Remove date filter"
                onClick={() => onDateModeChange('any')}
              >
                <X size={12} aria-hidden="true" />
              </button>
            </span>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
