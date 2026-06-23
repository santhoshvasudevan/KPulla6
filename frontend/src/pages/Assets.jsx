import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchHoldings } from '../api';
import { formatCurrency, formatPercent } from '../utils/formatters';
import { PieChart, Pie, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
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
  getChartLegendStyle,
} from '../components/charts/chartTheme';
import {
  holdingRowKey,
  holdingSymbolLabel,
  holdingAssetClassVariant,
} from '../utils/transactionDisplay';
import './Assets.css';
import { usePortfolio } from '../portfolioContext';

const ASSETS_SECTION_NAV = [
  { href: '#assets-holdings', label: 'Holdings' },
  { href: '#assets-allocation', label: 'Allocation' },
];

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
    return h.value_status === 'principal_only' && Number(h.current_value || 0) > 0;
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
        <span>{holdingSymbolLabel(h)}</span>
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
      {isFd ? (
        h.maturity_date ? (
          <span className="assets-table__symbol-meta">
            Matures {h.maturity_date}
            {h.status && h.status !== 'ACTIVE' ? ` · ${h.status}` : ''}
          </span>
        ) : null
      ) : null}
      {isMf && h.scheme_code && h.scheme_name ? (
        <span className="assets-table__symbol-meta">{h.scheme_code}</span>
      ) : null}
      {isMf && h.folio_number ? (
        <span className="assets-table__symbol-meta">Folio {h.folio_number}</span>
      ) : null}
      {h.holding_status === 'oversold' ? (
        <div className="assets-table__badges">
          <span title={h.warnings?.join(' ') || 'Sell quantity exceeded available lots'}>
            <StatusBadge status="oversold" />
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

  return (
    <tr
      key={rowKey}
      className={clickable ? 'assets-table__row-clickable' : undefined}
      onClick={clickable ? () => navigate(`/assets/${h.asset_symbol}`) : undefined}
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
        ) : (
          <StatusBadge status="warning" label="Price unavailable" />
        )}
      </AppTableCell>
      <AppTableCell numeric>
        <CurrencyValue value={h.current_value} currency={currency} />
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

  const [fxStatus, setFxStatus] = useState('ok');
  const [apiWarnings, setApiWarnings] = useState([]);

  const activeHoldings = useMemo(
    () => holdings.filter(isActiveHolding),
    [holdings]
  );
  const previousHoldings = useMemo(
    () => holdings.filter((h) => !isActiveHolding(h)),
    [holdings]
  );

  const cashAllocationRows = useMemo(
    () =>
      allocation.filter(
        (row) => row.is_cash || row.asset_type === 'CASH' || row.asset_type === 'BANK_CASH'
      ),
    [allocation]
  );

  const chartHoldings = useMemo(
    () =>
      allocation.filter(
        (h) => h.holding_status !== 'closed' && Number(h.current_value || 0) > 0
      ),
    [allocation]
  );

  const chartTotal = useMemo(
    () => chartHoldings.reduce((s, h) => s + Number(h.current_value || 0), 0),
    [chartHoldings]
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
      if (key === 'asset_symbol') return str(h.asset_symbol);
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

  const loadData = useCallback(() => {
    setLoading(true);
    setError('');
    fetchHoldings(apiQuery)
      .then((data) => {
        setHoldings(data.holdings || []);
        setAllocation(data.allocation || data.holdings || []);
        setFxStatus(data.fx_status || 'ok');
        setApiWarnings(data.warnings || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [apiQuery]);

  useEffect(() => {
    loadData();
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
        <KpiCard
          label="Active positions"
          value={String(activeHoldings.length)}
          helperText="Open holdings with quantity or value"
          size="compact"
        />
        <KpiCard
          label="Allocation slices"
          value={String(chartHoldings.length)}
          helperText="Positions included in allocation chart"
          size="compact"
        />
        {cashAllocationRows.length > 0 ? (
          <KpiCard
            label="Cash currencies"
            value={String(cashAllocationRows.length)}
            helperText="Portfolio cash rows from API"
            size="compact"
          />
        ) : null}
      </div>

      {showFxWarning ? (
        <WarningBanner
          severity="warning"
          message="FX unavailable for display currency conversion. Values are shown in each asset's transaction currency."
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
          <a key={item.href} className="assets-section-nav__link" href={item.href}>
            {item.label}
          </a>
        ))}
      </nav>

      <div className="assets-main">
        <div className="assets-main__table" id="assets-holdings">
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
                      label="Symbol"
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

        <aside className="assets-main__chart" id="assets-allocation">
          <ChartCard
            title="Allocation by Current Value"
            subtitle="Active holdings with available current value"
            className="assets-allocation-card"
            compact
          >
            {activeHoldings.length === 0 && chartHoldings.length === 0 ? (
              <EmptyState title="No active holdings to display." />
            ) : chartTotal <= 0 ? (
              <EmptyState
                title="Allocation chart unavailable until latest prices are synced."
                description={
                  hasMissingPrices
                    ? 'Latest prices are missing — run make refresh or use the backend refresh endpoint.'
                    : undefined
                }
              />
            ) : (
              <div className="assets-chart-panel">
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={chartHoldings}
                      dataKey="current_value"
                      nameKey="asset_symbol"
                      outerRadius={90}
                      innerRadius={55}
                      paddingAngle={2}
                      isAnimationActive={false}
                    >
                      {chartHoldings.map((_, idx) => (
                        <Cell key={idx} fill={getSeriesColor(idx)} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={getChartTooltipStyle()}
                      formatter={(value, _name, payload) => {
                        const pct = chartTotal > 0 ? Number(value) / chartTotal : 0;
                        const sym = payload?.payload?.asset_symbol || '';
                        const currency =
                          payload?.payload?.native_currency ||
                          payload?.payload?.currency ||
                          selectedDisplayCurrency ||
                          'EUR';
                        return [
                          `${formatCurrency(value, currency)} (${formatPercent(pct)})`,
                          sym,
                        ];
                      }}
                    />
                    <Legend wrapperStyle={getChartLegendStyle()} iconType="circle" />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </ChartCard>
        </aside>
      </div>

      {previousHoldings.length > 0 ? (
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
