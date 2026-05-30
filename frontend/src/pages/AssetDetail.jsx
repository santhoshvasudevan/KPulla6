import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchAssetDetails } from '../api';
import { usePortfolio } from '../portfolioContext';
import { formatCurrency } from '../utils/formatters';
import { AssetDetailMetricSheet } from '../components/metricSheet';
import {
  PageHeader,
  MetricCard,
  SectionCard,
  StatusBadge,
  WarningBanner,
  LoadingState,
  ErrorState,
  EmptyState,
  CurrencyValue,
  PercentValue,
} from '../components/ui';
import './AssetDetail.css';

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

  const headerSubtitle = [
    selectedPortfolioName || 'All Portfolios',
    selectedDisplayCurrency,
  ].join(' · ');

  return (
    <div className="asset-detail">
      <PageHeader
        title={data.asset_symbol}
        subtitle={headerSubtitle}
        breadcrumb={
          <Link to="/assets" className="asset-detail__breadcrumb-link">
            Assets
          </Link>
        }
      />

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
        <MetricCard
          label="Current Value"
          size="hero"
          value={
            <CurrencyValue value={data.current_value} currency={currency} />
          }
        />
        <MetricCard
          label="Quantity"
          value={<span className="asset-detail__quantity">{formatQuantity(qty)}</span>}
        />
        <MetricCard
          label="Unrealized P/L"
          tone={plTone(data.unrealized_pl)}
          value={
            <CurrencyValue
              value={data.unrealized_pl}
              currency={currency}
              tone={plTone(data.unrealized_pl)}
              showSign
            />
          }
        />
        <MetricCard
          label="XIRR"
          tone={plTone(data.xirr)}
          value={
            <PercentValue
              value={data.xirr}
              tone={plTone(data.xirr)}
              showSign
            />
          }
        />
      </div>

      <AssetDetailMetricSheet
        assetSymbol={data.asset_symbol || assetSymbol}
        apiQuery={apiQuery}
        folioNumber={data.folio_number || null}
        settingsLoaded={settingsLoaded}
      />

      <div className="asset-detail-sections">
        <SectionCard title="Position / Cost Basis">
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
        </SectionCard>

        <SectionCard title="Market / Valuation">
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
        </SectionCard>

        <SectionCard title="Data Quality / Warnings">
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
        </SectionCard>

        <SectionCard
          title="Transaction History"
          subtitle={
            transactions.length > 0
              ? `${transactions.length} transaction${transactions.length === 1 ? '' : 's'}`
              : undefined
          }
        >
          {transactions.length === 0 ? (
            <EmptyState
              title="No transactions"
              description="No transactions for this asset in the selected portfolio scope."
            />
          ) : (
            <div className="asset-detail-table-wrapper">
              <table className="asset-detail-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th className="num-col">Quantity</th>
                    <th className="num-col">Price/Share</th>
                    <th className="num-col">Fees</th>
                    <th>Currency</th>
                    <th>Split</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedTransactions.map((t) => (
                    <tr key={t.id}>
                      <td>{t.date}</td>
                      <td>
                        <span
                          className={`ui-txn-type ui-txn-type--${String(t.type || '').toLowerCase().replace(/_/g, '-')}`}
                        >
                          {t.type}
                        </span>
                      </td>
                      <td className="num-col">{formatQuantity(t.quantity)}</td>
                      <td className="num-col">
                        {t.price_per_share == null ? (
                          '—'
                        ) : (
                          formatCurrency(t.price_per_share, t.currency || currency)
                        )}
                      </td>
                      <td className="num-col">
                        {t.fees == null ? (
                          '—'
                        ) : (
                          formatCurrency(t.fees, t.currency || currency)
                        )}
                      </td>
                      <td>{t.currency || currency}</td>
                      <td>
                        {t.type === 'STOCK_SPLIT' && t.split_from && t.split_to
                          ? `${t.split_from}:${t.split_to}`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
