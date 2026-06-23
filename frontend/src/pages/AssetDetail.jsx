import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchAssetDetails } from '../api';
import { usePortfolio } from '../portfolioContext';
import { formatCurrency } from '../utils/formatters';
import { AssetDetailMetricSheet } from '../components/metricSheet';
import {
  PageHeader,
  KpiCard,
  AppCard,
  DataTableShell,
  AppTable,
  AppTableCell,
  AppTableHeaderCell,
  AssetClassPill,
  StatusBadge,
  WarningBanner,
  LoadingState,
  ErrorState,
  EmptyState,
  CurrencyValue,
  PercentValue,
} from '../components/ui';
import { holdingAssetClassVariant } from '../utils/transactionDisplay';
import './AssetDetail.css';

const ASSET_DETAIL_SECTION_NAV = [
  { href: '#asset-overview', label: 'Overview' },
  { href: '#asset-metrics', label: 'Metrics' },
  { href: '#asset-details', label: 'Details' },
  { href: '#asset-transactions', label: 'Transactions' },
];

function plTone(val) {
  if (val == null || Number.isNaN(Number(val))) return 'neutral';
  const n = Number(val);
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
  return 'neutral';
}

function kpiVariantFromTone(tone) {
  if (tone === 'positive') return 'gain';
  if (tone === 'negative') return 'loss';
  return 'neutral';
}

function formatQuantity(qty) {
  return Number(qty || 0).toFixed(4);
}

function assetClassFromDetail(data) {
  return holdingAssetClassVariant({
    asset_type: data?.asset_type,
    is_cash: data?.is_cash,
    primary_asset_class: data?.primary_asset_class,
  });
}

function DetailRow({ label, children }) {
  return (
    <div className="asset-detail__row">
      <dt className="asset-detail__row-label">{label}</dt>
      <dd className="asset-detail__row-value">{children}</dd>
    </div>
  );
}

export default function AssetDetail() {
  const { assetSymbol } = useParams();
  const { apiQuery, selectedPortfolioName, selectedDisplayCurrency, settingsLoaded } =
    usePortfolio();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = useCallback(() => {
    if (!settingsLoaded || !apiQuery) return;
    setLoading(true);
    setError('');
    fetchAssetDetails(assetSymbol, apiQuery)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [assetSymbol, apiQuery, settingsLoaded]);

  useEffect(() => {
    if (!settingsLoaded || !apiQuery) return;
    loadData();
  }, [loadData, settingsLoaded, apiQuery]);

  if (!settingsLoaded || loading) {
    return (
      <LoadingState
        message={
          !settingsLoaded ? 'Loading display settings…' : 'Loading asset details…'
        }
      />
    );
  }
  if (error) {
    return (
      <ErrorState
        title="Unable to load asset"
        message={error}
        onRetry={loadData}
      />
    );
  }
  if (!data) return null;

  const currency = data.currency || 'EUR';
  const qty = Number(data.cumulative_qty) || 0;
  const transactions = data.transactions || [];
  const sortedTransactions = [...transactions].sort((a, b) =>
    String(b.date).localeCompare(String(a.date))
  );
  const unrealizedTone = plTone(data.unrealized_pl);
  const xirrTone = plTone(data.xirr);

  const headerSubtitle = [
    selectedPortfolioName || 'All Portfolios',
    selectedDisplayCurrency,
    data.scheme_name || data.asset_type || 'Investment asset',
  ].join(' · ');

  return (
    <div className="asset-detail">
      <header className="asset-detail__hero" id="asset-overview">
        <PageHeader
          eyebrow={<AssetClassPill variant={assetClassFromDetail(data)} />}
          title={data.asset_symbol}
          subtitle={headerSubtitle}
          breadcrumb={
            <Link to="/assets" className="asset-detail__breadcrumb-link">
              Assets
            </Link>
          }
        />
      </header>

      {data.fx_status === 'fx_unavailable' ? (
        <WarningBanner
          severity="warning"
          message="FX unavailable for display currency conversion."
          className="asset-detail__banner"
        />
      ) : null}
      {(data.warnings || []).map((w) => (
        <WarningBanner
          key={w}
          severity="warning"
          message={w}
          className="asset-detail__banner"
        />
      ))}

      <div className="asset-detail-kpi-grid">
        <KpiCard
          label="Current Value"
          size="hero"
          value={<CurrencyValue value={data.current_value} currency={currency} />}
        />
        <KpiCard
          label="Quantity"
          value={<span className="asset-detail__quantity">{formatQuantity(qty)}</span>}
        />
        <KpiCard
          label="Unrealized P/L"
          variant={kpiVariantFromTone(unrealizedTone)}
          value={
            <CurrencyValue
              value={data.unrealized_pl}
              currency={currency}
              tone={unrealizedTone}
              showSign
            />
          }
        />
        <KpiCard
          label="XIRR"
          variant={kpiVariantFromTone(xirrTone)}
          value={
            <PercentValue value={data.xirr} tone={xirrTone} showSign />
          }
        />
      </div>

      <nav className="asset-detail-section-nav" aria-label="Asset detail section navigation">
        {ASSET_DETAIL_SECTION_NAV.map((item) => (
          <a key={item.href} className="asset-detail-section-nav__link" href={item.href}>
            {item.label}
          </a>
        ))}
      </nav>

      <div className="asset-detail-metric-sheet" id="asset-metrics">
        <AssetDetailMetricSheet
          assetSymbol={data.asset_symbol || assetSymbol}
          apiQuery={apiQuery}
          folioNumber={data.folio_number || null}
          settingsLoaded={settingsLoaded}
        />
      </div>

      <div className="asset-detail-sections" id="asset-details">
        <div className="asset-detail-sections__grid">
          <AppCard title="Position / Cost Basis" compact>
            <dl className="asset-detail__dl">
              <DetailRow label="Invested (FIFO)">
                <CurrencyValue
                  value={data.cumulative_invested_amount}
                  currency={currency}
                />
              </DetailRow>
              <DetailRow label="Avg Cost">
                <CurrencyValue value={data.avg_cost_per_share} currency={currency} />
              </DetailRow>
              <DetailRow label="Realized P/L">
                <CurrencyValue
                  value={data.realized_pl}
                  currency={currency}
                  tone={plTone(data.realized_pl)}
                  showSign
                />
              </DetailRow>
              <DetailRow label="Quantity">
                <span className="asset-detail__quantity">{formatQuantity(qty)}</span>
              </DetailRow>
            </dl>
          </AppCard>

          <AppCard title="Market / Valuation" compact>
            <dl className="asset-detail__dl">
              <DetailRow label="Latest Price">
                {data.current_price == null ? (
                  '—'
                ) : (
                  <CurrencyValue value={data.current_price} currency={currency} />
                )}
              </DetailRow>
              <DetailRow label="Current Value">
                <CurrencyValue value={data.current_value} currency={currency} />
              </DetailRow>
              <DetailRow label="Currency">{currency}</DetailRow>
            </dl>
          </AppCard>

          <AppCard title="Data Quality / Warnings" compact>
            <div className="asset-detail__status-row">
              {data.holding_status ? (
                <StatusBadge status={data.holding_status} />
              ) : null}
              {data.price_status ? (
                <StatusBadge status={data.price_status} />
              ) : null}
              {data.fx_status ? (
                <StatusBadge status={data.fx_status} />
              ) : null}
            </div>
          </AppCard>
        </div>

        <div id="asset-transactions">
          <DataTableShell
            className="asset-detail__transactions"
            title="Transaction History"
          subtitle={
            transactions.length > 0
              ? `${transactions.length} transaction${transactions.length === 1 ? '' : 's'}`
              : 'No transactions in this scope'
          }
          dense
          empty={transactions.length === 0}
          emptyTitle="No transactions"
          emptyDescription="No transactions for this asset in the selected portfolio scope."
        >
          {transactions.length > 0 ? (
            <AppTable compact className="asset-detail-table">
              <thead>
                <tr>
                  <AppTableHeaderCell>Date</AppTableHeaderCell>
                  <AppTableHeaderCell>Type</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Quantity</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Price/Share</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Fees</AppTableHeaderCell>
                  <AppTableHeaderCell>Currency</AppTableHeaderCell>
                  <AppTableHeaderCell>Split</AppTableHeaderCell>
                </tr>
              </thead>
              <tbody>
                {sortedTransactions.map((t) => (
                  <tr key={t.id}>
                    <AppTableCell>{t.date}</AppTableCell>
                    <AppTableCell>
                      <span
                        className={`ui-txn-type ui-txn-type--${String(t.type || '').toLowerCase().replace(/_/g, '-')}`}
                      >
                        {t.type}
                      </span>
                    </AppTableCell>
                    <AppTableCell numeric>{formatQuantity(t.quantity)}</AppTableCell>
                    <AppTableCell numeric>
                      {t.price_per_share == null ? (
                        '—'
                      ) : (
                        formatCurrency(t.price_per_share, t.currency || currency)
                      )}
                    </AppTableCell>
                    <AppTableCell numeric>
                      {t.fees == null ? (
                        '—'
                      ) : (
                        formatCurrency(t.fees, t.currency || currency)
                      )}
                    </AppTableCell>
                    <AppTableCell>{t.currency || currency}</AppTableCell>
                    <AppTableCell>
                      {t.type === 'STOCK_SPLIT' && t.split_from && t.split_to
                        ? `${t.split_from}:${t.split_to}`
                        : '—'}
                    </AppTableCell>
                  </tr>
                ))}
              </tbody>
            </AppTable>
          ) : null}
        </DataTableShell>
        </div>
      </div>
    </div>
  );
}
