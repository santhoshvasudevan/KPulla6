import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchHoldings } from '../api';
import { formatCurrency, formatPercent } from '../utils/formatters';
import { PieChart, Pie, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import {
  PageHeader,
  WarningBanner,
  LoadingState,
  ErrorState,
  EmptyState,
  StatusBadge,
  CurrencyValue,
  PercentValue,
  ChartCard,
  SectionCard,
  Button,
} from '../components/ui';
import {
  getSeriesColor,
  getChartTooltipStyle,
  getChartLegendStyle,
} from '../components/charts/chartTheme';
import { holdingRowKey, holdingSymbolLabel } from '../utils/transactionDisplay';
import './Assets.css';
import { usePortfolio } from '../portfolioContext';

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
    () =>
      holdings.filter(
        (h) => h.holding_status !== 'closed' && Number(h.quantity || 0) > 0
      ),
    [holdings]
  );
  const previousHoldings = useMemo(
    () =>
      holdings.filter(
        (h) => h.holding_status === 'closed' || Number(h.quantity || 0) === 0
      ),
    [holdings]
  );

  const cashAllocationRows = useMemo(
    () => allocation.filter((row) => row.is_cash || row.asset_type === 'CASH'),
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

  const hasMissingPrices = activeHoldings.some((h) => h.price_status === 'price_missing');

  const headerSubtitle = [
    selectedPortfolioName || 'All Portfolios',
    selectedDisplayCurrency,
  ].join(' · ');

  return (
    <div className="assets-page">
      <PageHeader title="Assets Overview" subtitle={headerSubtitle} />
      <p className="assets-page__description">
        A breakdown of all assets currently held in your portfolio. Latest prices come from cached
        historical data — run <code>make refresh</code> or use the backend refresh endpoint to sync.
      </p>

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
        <SectionCard
          className="assets-cash-balances"
          title="Cash balances"
          subtitle="Portfolio cash by currency — not an investment asset"
          compact
        >
          <div className="assets-table-wrapper">
            <table className="assets-table assets-cash-table">
              <thead>
                <tr>
                  <th>Currency</th>
                  <th className="num-col">Native balance</th>
                  <th className="num-col">Display value</th>
                </tr>
              </thead>
              <tbody>
                {cashAllocationRows.map((row) => {
                  const nativeCurrency = row.native_currency || row.currency || 'EUR';
                  const displayCurrency = row.currency || selectedDisplayCurrency || 'EUR';
                  return (
                    <tr key={`cash-${nativeCurrency}`} className="assets-cash-table__row">
                      <td className="symbol-col">{row.asset_symbol || `Cash ${nativeCurrency}`}</td>
                      <td className="num-col">
                        <CurrencyValue
                          value={row.native_balance ?? row.current_value}
                          currency={nativeCurrency}
                        />
                      </td>
                      <td className="num-col">
                        <CurrencyValue value={row.current_value} currency={displayCurrency} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}

      <div className="assets-main">
        <div className="assets-main__table">
          {activeHoldings.length === 0 ? (
            <EmptyState
              title="No assets found in portfolio."
              className="assets-page__table-empty"
            />
          ) : (
            <div className="assets-table-wrapper">
              <table className="assets-table">
                <thead>
                  <tr>
                    <th
                      className="assets-table__sortable"
                      onClick={() => toggleSort('asset_symbol')}
                    >
                      Symbol
                    </th>
                    <th
                      className="num-col assets-table__sortable"
                      onClick={() => toggleSort('quantity')}
                    >
                      Quantity
                    </th>
                    <th
                      className="num-col assets-table__sortable"
                      onClick={() => toggleSort('avg_cost')}
                    >
                      Avg Cost
                    </th>
                    <th
                      className="num-col assets-table__sortable"
                      onClick={() => toggleSort('current_price')}
                    >
                      Latest Price
                    </th>
                    <th
                      className="num-col assets-table__sortable"
                      onClick={() => toggleSort('current_value')}
                    >
                      Current Value
                    </th>
                    <th
                      className="num-col assets-table__sortable"
                      onClick={() => toggleSort('unrealized_pl')}
                    >
                      Unrealized P/L
                    </th>
                    <th className="num-col">XIRR</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedHoldings.map((h) => {
                    const currency = h.currency || 'EUR';
                    const avgCost = avgCostValue(h);
                    const unrealizedTone = plTone(h.unrealized_pl);
                    const isMf = h.asset_type === 'MUTUAL_FUND';
                    const rowKey = holdingRowKey(h);

                    return (
                      <tr
                        key={rowKey}
                        className="assets-table__row-clickable"
                        onClick={() => navigate(`/assets/${h.asset_symbol}`)}
                      >
                        <td className="symbol-col">
                          <div className="assets-table__symbol-cell">
                            <span>{holdingSymbolLabel(h)}</span>
                            {isMf && h.scheme_code && h.scheme_name ? (
                              <span className="assets-table__symbol-meta">{h.scheme_code}</span>
                            ) : null}
                            {isMf && h.folio_number ? (
                              <span className="assets-table__symbol-meta">Folio {h.folio_number}</span>
                            ) : null}
                            {(h.holding_status === 'oversold') && (
                              <div className="assets-table__badges">
                                <span
                                  title={
                                    h.warnings?.join(' ') ||
                                    'Sell quantity exceeded available lots'
                                  }
                                >
                                  <StatusBadge status="oversold" />
                                </span>
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="num-col">{formatQuantity(h.quantity)}</td>
                        <td className="num-col">
                          {avgCost == null || Number(h.quantity || 0) <= 0 ? (
                            '—'
                          ) : (
                            <CurrencyValue value={avgCost} currency={currency} />
                          )}
                        </td>
                        <td className="num-col">
                          {h.price_status === 'price_missing' ? (
                            <StatusBadge
                              status="price_missing"
                              label="Price missing — run refresh to fetch latest price"
                            />
                          ) : h.current_price != null ? (
                            <CurrencyValue value={h.current_price} currency={currency} />
                          ) : (
                            <StatusBadge status="warning" label="Price unavailable" />
                          )}
                        </td>
                        <td className="num-col">
                          <CurrencyValue value={h.current_value} currency={currency} />
                        </td>
                        <td className="num-col">
                          <CurrencyValue
                            value={h.unrealized_pl}
                            currency={currency}
                            tone={unrealizedTone}
                            showSign
                          />
                        </td>
                        <td className="num-col">
                          <PercentValue value={h.xirr} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <aside className="assets-main__chart">
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

      {previousHoldings.length > 0 && (
        <SectionCard
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
            <div className="assets-table-wrapper assets-previous__table">
              <table className="assets-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th className="num-col">Quantity</th>
                    <th className="num-col">Invested</th>
                    <th className="num-col">Realized P/L</th>
                    <th className="num-col">Current Value</th>
                    <th className="num-col">XIRR</th>
                  </tr>
                </thead>
                <tbody>
                  {previousHoldings.map((h) => {
                    const currency = h.currency || 'EUR';
                    const isMf = h.asset_type === 'MUTUAL_FUND';
                    return (
                      <tr key={`closed-${holdingRowKey(h)}`}>
                        <td className="symbol-col">
                          <div className="assets-table__symbol-cell">
                            <span>{holdingSymbolLabel(h)}</span>
                            {isMf && h.folio_number ? (
                              <span className="assets-table__symbol-meta">Folio {h.folio_number}</span>
                            ) : null}
                            {h.holding_status === 'closed' ? (
                              <div className="assets-table__badges">
                                <StatusBadge status="closed" />
                              </div>
                            ) : null}
                          </div>
                        </td>
                        <td className="num-col">0.0000</td>
                        <td className="num-col">
                          <CurrencyValue value={h.invested || 0} currency={currency} />
                        </td>
                        <td className="num-col">
                          <CurrencyValue
                            value={h.realized_pl || 0}
                            currency={currency}
                            tone={plTone(h.realized_pl)}
                            showSign
                          />
                        </td>
                        <td className="num-col">
                          <CurrencyValue value={0} currency={currency} />
                        </td>
                        <td className="num-col">
                          <PercentValue value={h.xirr} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </SectionCard>
      )}
    </div>
  );
}
