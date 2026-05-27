const API_ROOT = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const BASE_URL = `${API_ROOT}/api/v1`;

let _dashboardSummaryCacheByScope = new Map();

function buildUrl(path, params) {
  const qs = params ? `?${params.toString()}` : '';
  return `${BASE_URL}${path}${qs}`;
}

export async function fetchWithHandling(path, options = {}) {
  const response = await fetch(buildUrl(path), options);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const detail = errorData.detail;
    let message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
          : errorData.message || '';
    if (!message && typeof errorData === 'object') {
      const fieldMsgs = Object.entries(errorData)
        .filter(([key]) => key !== 'detail' && key !== 'message')
        .map(([key, val]) => {
          const text = Array.isArray(val) ? val.join(', ') : String(val);
          return `${key}: ${text}`;
        });
      if (fieldMsgs.length) message = fieldMsgs.join('; ');
    }
    if (!message) message = `Request failed (${response.status})`;
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function _scopeKey(scopeParams) {
  if (!scopeParams) return 'portfolio_scope=all';
  const parts = [];
  if (scopeParams.portfolio_id != null) {
    parts.push(`portfolio_id=${scopeParams.portfolio_id}`);
  } else {
    parts.push('portfolio_scope=all');
  }
  parts.push(`display_currency=${encodeURIComponent(scopeParams.display_currency || 'EUR')}`);
  return parts.join('&');
}

export function withScopeParams(params, scopeParams) {
  const out = new URLSearchParams(params || {});
  if (scopeParams?.portfolio_id != null) {
    out.set('portfolio_id', String(scopeParams.portfolio_id));
  } else {
    out.set('portfolio_scope', 'all');
  }
  out.set('display_currency', String(scopeParams?.display_currency || 'EUR'));
  return out;
}

export async function fetchHealth() {
  return fetchWithHandling('/health');
}

export async function fetchPortfolios() {
  return fetchWithHandling('/portfolios');
}

export async function createPortfolio(data) {
  return fetchWithHandling('/portfolios', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function updatePortfolio(id, data) {
  return fetchWithHandling(`/portfolios/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function deletePortfolio(id) {
  return fetchWithHandling(`/portfolios/${id}`, { method: 'DELETE' });
}

export async function fetchTransactions(page = 1, pageSize = 20, scopeParams = null) {
  const params = withScopeParams({ page, page_size: pageSize }, scopeParams);
  return fetchWithHandling(`/transactions?${params.toString()}`);
}

export function invalidateDashboardSummaryCache() {
  _dashboardSummaryCacheByScope = new Map();
}

export async function fetchDashboardSummary(scopeParams = null) {
  const key = _scopeKey(scopeParams);
  if (_dashboardSummaryCacheByScope.has(key)) {
    return _dashboardSummaryCacheByScope.get(key);
  }
  const params = withScopeParams({}, scopeParams);
  const p = fetchWithHandling(`/portfolio/summary?${params.toString()}`);
  _dashboardSummaryCacheByScope.set(key, p);
  return p;
}

export async function fetchHoldings(scopeParams = null) {
  const params = withScopeParams({}, scopeParams);
  return fetchWithHandling(`/portfolio/holdings?${params.toString()}`);
}

export async function fetchPortfolioPerformance(
  metric = 'value',
  benchmarkSymbol = null,
  range = '1Y',
  scopeParams = null
) {
  const params = withScopeParams({ metric, range }, scopeParams);
  if (benchmarkSymbol && (metric === 'cumulative_return' || metric === 'twror')) {
    params.set('benchmark', benchmarkSymbol);
  }
  return fetchWithHandling(`/portfolio/performance?${params.toString()}`);
}

export async function fetchBenchmarkIndices() {
  const data = await fetchWithHandling('/benchmarks/indices');
  return data.indices || [];
}

export async function fetchAssetDetails(assetSymbol, scopeParams = null) {
  const sym = encodeURIComponent(assetSymbol);
  const params = withScopeParams({}, scopeParams);
  return fetchWithHandling(`/portfolio/assets/${sym}?${params.toString()}`);
}

export async function createTransaction(data) {
  const res = await fetchWithHandling('/transactions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  invalidateDashboardSummaryCache();
  return res;
}

export async function updateTransaction(id, data) {
  const res = await fetchWithHandling(`/transactions/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  invalidateDashboardSummaryCache();
  return res;
}

export async function deleteTransaction(id) {
  const res = await fetchWithHandling(`/transactions/${id}`, { method: 'DELETE' });
  invalidateDashboardSummaryCache();
  return res;
}

export async function importTransactionsCsv(file, portfolioId = null) {
  const formData = new FormData();
  formData.append('file', file);
  const qs = portfolioId != null ? `?portfolio_id=${encodeURIComponent(String(portfolioId))}` : '';
  const response = await fetch(buildUrl(`/transactions/import-csv${qs}`), {
    method: 'POST',
    body: formData,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.message || 'Import failed');
  }
  invalidateDashboardSummaryCache();
  return data;
}

export async function getSettings() {
  return fetchWithHandling('/settings');
}

export async function updateSettings(data) {
  const res = await fetchWithHandling('/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  invalidateDashboardSummaryCache();
  return res;
}

export async function refreshPrices() {
  return fetchWithHandling('/prices/refresh', { method: 'POST' });
}

export async function forceSyncPortfolio() {
  return fetchWithHandling('/portfolio/force-sync', { method: 'POST' });
}
