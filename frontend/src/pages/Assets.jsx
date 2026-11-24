import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchHoldings } from '../api';
import { formatCurrency, formatPercent } from '../utils/formatters';
import { PieChart, Pie, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import {
  PageHeader,
  DataTableShell,
  AppTable,
  AppTableCell,
  AppTableHeaderCell,
  WarningBanner,
  LoadingState,
  ErrorState,
  EmptyState,
  StatusBadge,
  AssetClassPill,
  CurrencyValue,
  PercentValue,
  ChartCard,
  AppCard,
  Button,
  KpiCard,
} from '../components/ui';
import {
  getSeriesColor,
  getChartTooltipStyle,
} from '../components/charts/chartTheme';
import {
  holdingRowKey,
  holdingSymbolLabel,
  holdingAssetClassVariant,
} from '../utils/transactionDisplay';
import AssetsBreakdowns from './AssetsBreakdowns';
import './Assets.css';
import { usePortfolio } from '../portfolioContext';

const ASSETS_SECTION_NAV = [
  { href: '#assets-allocation', label: 'Allocation' },
  { href: '#assets-holdings', label: 'Holdings' },
];

const INVESTMENT_TYPES = {
  MUTUAL_FUND: 'Mutual Funds',
  STOCK: 'Stocks',
  FIXED_DEPOSIT: 'Fixed Deposits',
};

function investmentType(holding) {
  return holding.asset_type || 'STOCK';
}

function matchesInvestmentFilter(holding, filter) {
  if (filter === 'all') return true;
  if (filter === 'equity' || filter === 'debt') return holding.overview_class === filter;
  return investmentType(holding) === filter;
}

function plTone(val) {
  if (val == null || Number.isNaN(Number(val))) return 'neutral';
  const n = Number(val);
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
  return 'neutral';
}

function formatQuantity(qty) {
  return Number(qty || 0).toFixed(4);
}

function isFixedDepositHolding(h) {
  return h?.asset_type === 'FIXED_DEPOSIT';
}

function isBankCashHolding(h) {
  return h?.asset_type === 'BANK_CASH';
}

function isActiveHolding(h) {
  if (h.holding_status === 'closed') return false;
  if (isBankCashHolding(h)) {
    return Number(h.current_value || 0) > 0;
  }
  if (isFixedDepositHolding(h)) {
    return h.value_status === 'principal_only';
  }
  return Number(h.quantity || 0) > 0;
}

function avgCostValue(h) {
  if (h.avg_cost_per_share != null && !Number.isNaN(Number(h.avg_cost_per_share))) {
    return Number(h.avg_cost_per_share);
  }
  const qty = Number(h.quantity || 0);
  if (qty > 0 && h.invested != null && !Number.isNaN(Number(h.invested))) {
    return Number(h.invested) / qty;
  }
  return null;
}

function sortAvgCost(h) {
  const avg = avgCostValue(h);
  return avg == null ? 0 : avg;
}

function SortableHeader({ label, sortKey, sort, onSort, numeric = false }) {
  return (
    <AppTableHeaderCell
      numeric={numeric}
      className="assets-table__sortable"
      onClick={() => onSort(sortKey)}
      aria-sort={
        sort.key === sortKey
          ? sort.direction === 'asc'
            ? 'ascending'
            : 'descending'
          : 'none'
      }
    >
      {label}
    </AppTableHeaderCell>
  );
}

function HoldingSymbolCell({ holding: h }) {
  const isMf = h.asset_type === 'MUTUAL_FUND';
  const isFd = isFixedDepositHolding(h);
  const isBankCash = isBankCashHolding(h);

  return (
    <div className="assets-table__symbol-cell">
      <div className="assets-table__symbol-primary">
        <AssetClassPill variant={holdingAssetClassVariant(h)} />
        <span>{h.asset_name || (isFd ? h.institution_name || "Fixed Deposit" : holdingSymbolLabel(h))}</span>
      </div>
      {isBankCash ? (
        <>
          <span className="assets-table__symbol-meta">Bank Cash</span>
          {h.institution_name ? (
            <span className="assets-table__symbol-meta">
              {h.institution_name}
              {h.account_number ? ` · ${h.account_number}` : ''}
            </span>
          ) : null}
        </>
      ) : null}
      {h.asset_name && h.asset_name !== h.asset_symbol && (
        <span className="assets-table__symbol-meta">{h.asset_symbol}</span>
      )}
      {isFd ? (
        h.maturity_date || h.deposit_account_number ? (
          <span className="assets-table__symbol-meta">
            {[h.deposit_account_number, h.maturity_date && `Matures ${h.maturity_date}`].filter(Boolean).join(" · ")}
            {h.status && h.status !== 'ACTIVE' ? ` · ${h.status}` : ''}
          </span>
        ) : null
      ) : null}
      {isMf && (h.scheme_code || h.folio_number) && (
        <span className="assets-table__symbol-meta">
          {[h.scheme_name && h.scheme_code, h.folio_number && `Folio ${h.folio_number}`]
            .filter(Boolean).join(' · ')}
        </span>
      )}
      {h.holding_status === 'oversold' ? (
        <div className="assets-table__badges">
          <span title={h.warnings?.join(' ') || 'Sell quantity exceeded available lots'}>
            <StatusBadge status="oversold" />
          </span>
        </div>
      ) : null}
      {h.nav_provisional ? (
        <div className="assets-table__badges">
          <span title={h.warnings?.join(' ') || 'Valued with an unverified provisional NAV'}>
            <StatusBadge status="warning" label="Provisional NAV" />
          </span>
        </div>
      ) : null}
    </div>
  );
}

function renderHoldingRow(h, navigate) {
  const currency = h.currency || 'EUR';
  const avgCost = avgCostValue(h);
  const unrealizedTone = plTone(h.unrealized_pl);
  const isFd = isFixedDepositHolding(h);
  const isBankCash = isBankCashHolding(h);
  const rowKey = holdingRowKey(h);
  const clickable = !isFd && !isBankCash;
  const assetPath = `/assets/${encodeURIComponent(h.asset_symbol)}`;
  const folioQuery = h.folio_number ? `?${new URLSearchParams({ folio_number: h.folio_number })}` : '';

  return (
    <tr
      key={rowKey}
      className={clickable ? 'assets-table__row-clickable' : undefined}
      onClick={clickable ? () => navigate(assetPath + folioQuery) : undefined}
    >
      <AppTableCell className="assets-table__symbol">
        <HoldingSymbolCell holding={h} />
      </AppTableCell>
      <AppTableCell numeric>
        {isFd || isBankCash ? '—' : formatQuantity(h.quantity)}
      </AppTableCell>
      <AppTableCell numeric>
        {isFd || isBankCash ? (
          '—'
        ) : avgCost == null || Number(h.quantity || 0) <= 0 ? (
          '—'
        ) : (
          <CurrencyValue value={avgCost} currency={currency} />
        )}
      </AppTableCell>
      <AppTableCell numeric>
        {isFd || isBankCash ? (
          '—'
        ) : h.price_status === 'price_missing' ? (
          <StatusBadge
            status="price_missing"
            label="Price missing — run refresh to fetch latest price"
          />
        ) : h.current_price != null ? (
          <CurrencyValue value={h.current_price} currency={currency} />
        ) : h.nav_source === 'MIXED' ? (
          <StatusBadge status="info" label="Mixed NAVs" />
        ) : (
          <StatusBadge status="warning" label="Price unavailable" />
        )}
      </AppTableCell>
      <AppTableCell numeric>
        <CurrencyValue value={h.current_value} currency={h.display_currency || currency} />
      </AppTableCell>
      <AppTableCell numeric>
        {isFd || isBankCash ? (
          '—'
        ) : (
          <CurrencyValue
            value={h.unrealized_pl}
            currency={currency}
            tone={unrealizedTone}
            showSign
          />
        )}
      </AppTableCell>
      <AppTableCell numeric>
        {isFd || isBankCash ? '—' : <PercentValue value={h.xirr} />}
      </AppTableCell>
    </tr>
  );
}

export default function Assets() {
  const navigate = useNavigate();
  const { apiQuery, selectedPortfolioName, selectedDisplayCurrency } = usePortfolio();
  const [holdings, setHoldings] = useState([]);
  const [allocation, setAllocation] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sort, setSort] = useState({ key: 'current_value', direction: 'desc' });
  const [showPrevious, setShowPrevious] = useState(false);
  const [investmentFilter, setInvestmentFilter] = useState('all');
  const [overview, setOverview] = useState({});
  const [reports, setReports] = useState(null);
  const [grouping, setGrouping] = useState('scheme');
  const [selection, setSelection] = useState(null);
  const [section, setSection] = useState('holdings');

  const [fxStatus, setFxStatus] = useState('ok');
  const [apiWarnings, setApiWarnings] = useState([]);
  const [navProvisional, setNavProvisional] = useState(false);

  const scopedInvestments = useMemo(
    () => holdings.filter((h) => isActiveHolding(h) && !isBankCashHolding(h)),
    [holdings]
  );
  const types = [...new Set(scopedInvestments.map(investmentType))];
  const filterOptions = [
    ['all', 'All Investments'],
    ...types.map((type) => [type, INVESTMENT_TYPES[type] || type.replaceAll('_', ' ')]),
    ['equity', 'Equity'],
    ['debt', 'Debt'],
  ];
  const filter = filterOptions.some(([key]) => key === investmentFilter) ? investmentFilter : 'all';
  useEffect(() => {
    if (filter !== investmentFilter) setInvestmentFilter(filter);
  }, [filter, investmentFilter]);
  const filteredHoldings = scopedInvestments.filter((h) => matchesInvestmentFilter(h, filter));
  const view = reports?.[filter];
  const allocationGrouping = filter === 'MUTUAL_FUND' ? grouping : 'scheme';
  const chartHoldings = reports
    ? view?.allocation?.[allocationGrouping] || []
    : allocation.flatMap((holding) => {
      if (holding.is_cash || ['CASH', 'BANK_CASH'].includes(holding.asset_type) ||
          !isActiveHolding(holding) || !matchesInvestmentFilter(holding, filter)) return [];
      const value = Object.hasOwn(holding, 'display_current_value')
        ? holding.display_current_value
        : (holding.display_currency || holding.currency) === selectedDisplayCurrency
          ? holding.current_value : null;
      if (!(Number(value) > 0)) return [];
      const key = holdingRowKey(holding);
      return [{ id: key, name: holding.asset_name || holdingSymbolLabel(holding),
        value, holding_keys: [key] }];
    });
  const selectedSlice = selection?.apiQuery === apiQuery &&
    selection.filter === filter && selection.grouping === allocationGrouping
    ? chartHoldings.find((slice) => slice.id === selection.id)
    : null;
  const activeHoldings = selectedSlice
    ? filteredHoldings.filter((h) => selectedSlice.holding_keys.includes(holdingRowKey(h)))
    : filteredHoldings;
  function selectSlice(slice) {
    setSelection(selectedSlice?.id === slice.id ? null : {
      id: slice.id, apiQuery, filter, grouping: allocationGrouping,
    });
    setSection('holdings');
  }
  const bankCashHoldings = holdings.filter((h) => isBankCashHolding(h) && isActiveHolding(h));
  const previousHoldings = useMemo(
    () => holdings.filter((h) => !isActiveHolding(h)),
    [holdings]
  );

  const cashAllocationRows = useMemo(
    () =>
      allocation.filter(
        (row) => row.is_cash || row.asset_type === 'CASH'
      ),
    [allocation]
  );

  const showFxWarning = useMemo(() => {
    if (fxStatus !== 'fx_unavailable') return false;
    const display = String(selectedDisplayCurrency || 'EUR').toUpperCase();
    return activeHoldings.some(
      (h) => String(h.currency || 'EUR').toUpperCase() !== display
    );
  }, [fxStatus, selectedDisplayCurrency, activeHoldings]);

  const sortedHoldings = [...activeHoldings].sort((a, b) => {
    const key = sort.key;
    const dir = sort.direction === 'asc' ? 1 : -1;

    const num = (v) => (v == null || Number.isNaN(Number(v)) ? 0 : Number(v));
    const str = (v) => String(v || '');

    const getValue = (h) => {
      if (key === 'asset_symbol') return str(holdingSymbolLabel(h));
      if (key === 'quantity') return num(h.quantity);
      if (key === 'avg_cost') return sortAvgCost(h);
      if (key === 'current_price') return num(h.current_price);
      if (key === 'current_value') return num(h.current_value);
      if (key === 'unrealized_pl') return num(h.unrealized_pl);
      return 0;
    };

    const av = getValue(a);
    const bv = getValue(b);
    if (typeof av === 'string' || typeof bv === 'string') {
      return av.localeCompare(bv) * dir;
    }
    return (av - bv) * dir;
  });

  const toggleSort = (key) => {
    setSort((prev) => {
      if (prev.key !== key) return { key, direction: 'desc' };
      return { key, direction: prev.direction === 'desc' ? 'asc' : 'desc' };
    });
  };

  const latestRequest = useRef(0);
  const loadData = useCallback(({ background = false } = {}) => {
    const request = ++latestRequest.current;
    if (!background) setLoading(true);
    setError('');
    fetchHoldings(apiQuery)
      .then((data) => {
        if (request !== latestRequest.current) return;
        setHoldings(data.holdings || []);
        setOverview(data.assets_overview || {});
        setReports(data.assets_reports || null);
        setSelection(null);
        setAllocation(data.allocation || data.holdings || []);
        setFxStatus(data.fx_status || 'ok');
        setApiWarnings(data.warnings || []);
        setNavProvisional(Boolean(data.nav_provisional));
        setLoading(false);
      })
      .catch((err) => {
        if (request !== latestRequest.current) return;
        setError(err.message);
        setLoading(false);
      });
  }, [apiQuery]);

  useEffect(() => {
    loadData();
    return () => { latestRequest.current += 1; };
  }, [loadData]);

  if (loading) return <LoadingState message="Loading holdings…" />;
  if (error) {
    return (
      <ErrorState
        title="Unable to load holdings"
        message={error}
        onRetry={loadData}
      />
    );
  }

  const hasMissingPrices = activeHoldings.some(
    (h) => !isFixedDepositHolding(h) && h.price_status === 'price_missing'
  );

  const headerSubtitle = [
    selectedPortfolioName || 'All Portfolios',
    selectedDisplayCurrency,
    `${activeHoldings.length} active ${activeHoldings.length === 1 ? 'position' : 'positions'}`,
  ].join(' · ');

  return (
    <div className="assets-page">
      <PageHeader title="Assets Overview" subtitle={headerSubtitle} />

      <p className="assets-page__description">
        Holdings and allocation from the backend portfolio view. Latest prices come from cached
        historical data — run <code>make refresh</code> or use the backend refresh endpoint to sync.
      </p>

      <div className="assets-page__overview" aria-label="Holdings overview">
        {['equity', 'debt', 'cash'].map((key) => (
          <KpiCard
            key={key}
            label={`${key[0].toUpperCase()}${key.slice(1)} total`}
            value={overview[key] == null ? '—' : formatCurrency(overview[key], selectedDisplayCurrency || 'EUR')}
            helperText={overview[key] === null ? 'Valuation incomplete' : undefined}
            size="compact"
          />
        ))}
      </div>

      <div className="assets-section-nav" role="group" aria-label="Investment filters">
        {filterOptions.map(([key, label]) => (
          <Button key={key} variant={filter === key ? 'primary' : 'secondary'}
            aria-pressed={filter === key} onClick={() => { setInvestmentFilter(key); setGrouping('scheme'); setSelection(null); }}>
            {label}
          </Button>
        ))}
      </div>

      {showFxWarning ? (
        <WarningBanner
          severity="warning"
          message="FX unavailable for display currency conversion. Values are shown in each asset's transaction currency."
          className="assets-page__banner"
        />
      ) : null}

      {navProvisional ? (
        <WarningBanner
          severity="warning"
          message="Some mutual fund holdings are valued with unverified provisional NAVs until cached provider NAVs are available."
          className="assets-page__banner"
        />
      ) : null}

      {apiWarnings.map((w) => (
        <WarningBanner key={w} severity="warning" message={w} className="assets-page__banner" />
      ))}

      {cashAllocationRows.length > 0 ? (
        <DataTableShell
          className="assets-cash-balances"
          title="Cash balances"
          subtitle="Portfolio cash by currency — not an investment asset"
          dense
        >
          <AppTable compact className="assets-cash-table">
            <thead>
              <tr>
                <AppTableHeaderCell>Currency</AppTableHeaderCell>
                <AppTableHeaderCell numeric>Native balance</AppTableHeaderCell>
                <AppTableHeaderCell numeric>Display value</AppTableHeaderCell>
              </tr>
            </thead>
            <tbody>
              {cashAllocationRows.map((row) => {
                const nativeCurrency = row.native_currency || row.currency || 'EUR';
                const displayCurrency = row.currency || selectedDisplayCurrency || 'EUR';
                return (
                  <tr key={`cash-${nativeCurrency}`} className="assets-cash-table__row">
                    <AppTableCell>
                      <div className="assets-table__symbol-primary">
                        <AssetClassPill variant="cash" />
                        <span>{row.asset_symbol || `Cash ${nativeCurrency}`}</span>
                      </div>
                    </AppTableCell>
                    <AppTableCell numeric>
                      <CurrencyValue
                        value={row.native_balance ?? row.current_value}
                        currency={nativeCurrency}
                      />
                    </AppTableCell>
                    <AppTableCell numeric>
                      <CurrencyValue value={row.current_value} currency={displayCurrency} />
                    </AppTableCell>
                  </tr>
                );
              })}
            </tbody>
          </AppTable>
        </DataTableShell>
      ) : null}

      <nav className="assets-section-nav" aria-label="Assets section navigation">
        {ASSETS_SECTION_NAV.map((item) => (
          <a key={item.href} className="assets-section-nav__link" href={item.href}
            onClick={() => { if (item.href === '#assets-holdings') setSection('holdings'); }}>
            {item.label}
          </a>
        ))}
      </nav>

      {bankCashHoldings.length > 0 && (
        <DataTableShell title="Bank cash balances" dense>
          <AppTable compact>
            <thead><tr>
              <AppTableHeaderCell>Account</AppTableHeaderCell>
              <AppTableHeaderCell numeric>Display value</AppTableHeaderCell>
            </tr></thead>
            <tbody>{bankCashHoldings.map((h) => (
              <tr key={holdingRowKey(h)}>
                <AppTableCell><HoldingSymbolCell holding={h} /></AppTableCell>
                <AppTableCell numeric>
                  <CurrencyValue value={h.current_value} currency={h.display_currency || h.currency} />
                </AppTableCell>
              </tr>
            ))}</tbody>
          </AppTable>
        </DataTableShell>
      )}

      <div className="assets-main">
        <aside className="assets-main__chart" id="assets-allocation">
          <ChartCard
            title="Allocation by Current Value"
            subtitle="Active holdings with available current value"
            className="assets-allocation-card"
            compact
          >
            {filter === 'MUTUAL_FUND' && (
              <div className="assets-section-nav" role="group" aria-label="Allocation grouping">
                {[['scheme', 'By scheme'], ['folio', 'By folio']].map(([key, label]) => (
                  <Button key={key} variant="secondary" aria-pressed={grouping === key}
                    onClick={() => { setGrouping(key); setSelection(null); }}>
                    {label}
                  </Button>
                ))}
              </div>
            )}
            {view?.allocation?.incomplete && <p>Allocation includes positions with an available value.</p>}
            {filteredHoldings.length === 0 && chartHoldings.length === 0 ? (
              <EmptyState title="No active holdings to display." />
            ) : chartHoldings.length === 0 ? (
              <EmptyState
                title={hasMissingPrices ? "Allocation chart unavailable until latest prices are synced." : "No valued holdings for this allocation."}
                description={
                  hasMissingPrices
                    ? 'Latest prices are missing — run make refresh or use the backend refresh endpoint.'
                    : undefined
                }
              />
            ) : (
              <div className="assets-chart-panel">
                <div className="assets-chart-canvas">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={chartHoldings}
                      dataKey="value"
                      nameKey="name"
                      onClick={(slice) => selectSlice(slice.payload || slice)}
                      cursor="pointer"
                      outerRadius="92%"
                      innerRadius="47%"
                      paddingAngle={0.5}
                      isAnimationActive={false}
                    >
                      {chartHoldings.map((slice, idx) => (
                        <Cell key={slice.id} fill={getSeriesColor(idx)}
                          opacity={selectedSlice && selectedSlice.id !== slice.id ? 0.35 : 1} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={getChartTooltipStyle()}
                      formatter={(value, name, item) => [
                        `${formatCurrency(value, selectedDisplayCurrency || 'EUR')}${item?.payload?.weight == null ? '' : ` (${formatPercent(item.payload.weight)})`}`,
                        name,
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
                </div>
                <details className="assets-allocation-options">
                  <summary>Browse allocation holdings ({chartHoldings.length})</summary>
                <div className="assets-allocation-legend" aria-label="Allocation holdings">
                  {chartHoldings.map((slice, idx) => (
                    <Button key={slice.id} variant="secondary" aria-pressed={selectedSlice?.id === slice.id}
                      onClick={() => selectSlice(slice)}>
                      <span className="assets-allocation-legend__dot" style={{ background: getSeriesColor(idx) }} />
                      {slice.name}{slice.weight == null ? '' : ` · ${formatPercent(slice.weight)}`}
                    </Button>
                  ))}
                </div>
                </details>
              </div>
            )}
          </ChartCard>
        </aside>
        <div className="assets-section-nav" role="group" aria-label="Assets views">
          <Button variant={section === 'holdings' ? 'primary' : 'secondary'} aria-pressed={section === 'holdings'}
            onClick={() => setSection('holdings')}>Holdings</Button>
          <Button variant={section === 'breakdowns' ? 'primary' : 'secondary'} aria-pressed={section === 'breakdowns'}
            onClick={() => setSection('breakdowns')}>Breakdowns</Button>
        </div>
        {section === 'breakdowns' ? (
          <AssetsBreakdowns onChanged={() => loadData({ background: true })} report={view?.funds} currency={selectedDisplayCurrency || 'EUR'} />
        ) : (
          <div className="assets-main__table" id="assets-holdings">
            {selectedSlice && (
              <div className="assets-section-nav">
                <span>Showing {selectedSlice.name}</span>
                <Button variant="secondary" onClick={() => setSelection(null)}>Clear allocation selection</Button>
              </div>
            )}
            <DataTableShell
              title="Holdings"
              subtitle="Click a row to open asset detail"
              dense
              empty={activeHoldings.length === 0}
              emptyTitle="No assets found in portfolio."
            >
              {activeHoldings.length > 0 ? (
                <AppTable compact className="assets-table">
                  <thead>
                    <tr>
                      <SortableHeader
                        label="Holding"
                        sortKey="asset_symbol"
                        sort={sort}
                        onSort={toggleSort}
                      />
                      <SortableHeader
                        label="Quantity"
                        sortKey="quantity"
                        sort={sort}
                        onSort={toggleSort}
                        numeric
                      />
                      <SortableHeader
                        label="Avg Cost"
                        sortKey="avg_cost"
                        sort={sort}
                        onSort={toggleSort}
                        numeric
                      />
                      <SortableHeader
                        label="Latest Price"
                        sortKey="current_price"
                        sort={sort}
                        onSort={toggleSort}
                        numeric
                      />
                      <SortableHeader
                        label="Current Value"
                        sortKey="current_value"
                        sort={sort}
                        onSort={toggleSort}
                        numeric
                      />
                      <SortableHeader
                        label="Unrealized P/L"
                        sortKey="unrealized_pl"
                        sort={sort}
                        onSort={toggleSort}
                        numeric
                      />
                      <AppTableHeaderCell numeric>XIRR</AppTableHeaderCell>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedHoldings.map((h) => renderHoldingRow(h, navigate))}
                  </tbody>
                </AppTable>
              ) : null}
            </DataTableShell>
          </div>
        )}
      </div>

      {section === 'holdings' && previousHoldings.length > 0 ? (
        <AppCard
          className="assets-previous"
          title="Previous holdings"
          subtitle={`${previousHoldings.length} closed or zero-quantity ${previousHoldings.length === 1 ? 'position' : 'positions'}`}
          actions={
            <Button variant="secondary" onClick={() => setShowPrevious((v) => !v)}>
              {showPrevious ? 'Hide previous holdings' : 'Show previous holdings'}
            </Button>
          }
          compact
        >
          {showPrevious ? (
            <DataTableShell className="assets-previous__table" dense>
              <AppTable compact className="assets-table">
                <thead>
                  <tr>
                    <AppTableHeaderCell>Symbol</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Quantity</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Invested</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Realized P/L</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>Current Value</AppTableHeaderCell>
                    <AppTableHeaderCell numeric>XIRR</AppTableHeaderCell>
                  </tr>
                </thead>
                <tbody>
                  {previousHoldings.map((h) => {
                    const currency = h.currency || 'EUR';
                    const isMf = h.asset_type === 'MUTUAL_FUND';
                    return (
                      <tr key={`closed-${holdingRowKey(h)}`}>
                        <AppTableCell>
                          <div className="assets-table__symbol-cell">
                            <div className="assets-table__symbol-primary">
                              <AssetClassPill variant={holdingAssetClassVariant(h)} />
                              <span>{holdingSymbolLabel(h)}</span>
                            </div>
                            {isMf && h.folio_number ? (
                              <span className="assets-table__symbol-meta">
                                Folio {h.folio_number}
                              </span>
                            ) : null}
                            {h.holding_status === 'closed' ? (
                              <div className="assets-table__badges">
                                <StatusBadge status="closed" />
                              </div>
                            ) : null}
                          </div>
                        </AppTableCell>
                        <AppTableCell numeric>0.0000</AppTableCell>
                        <AppTableCell numeric>
                          <CurrencyValue value={h.invested || 0} currency={currency} />
                        </AppTableCell>
                        <AppTableCell numeric>
                          <CurrencyValue
                            value={h.realized_pl || 0}
                            currency={currency}
                            tone={plTone(h.realized_pl)}
                            showSign
                          />
                        </AppTableCell>
                        <AppTableCell numeric>
                          <CurrencyValue value={0} currency={currency} />
                        </AppTableCell>
                        <AppTableCell numeric>
                          <PercentValue value={h.xirr} />
                        </AppTableCell>
                      </tr>
                    );
                  })}
                </tbody>
              </AppTable>
            </DataTableShell>
          ) : null}
        </AppCard>
      ) : null}
    </div>
  );
}
