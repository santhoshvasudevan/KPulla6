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

export async function fetchTransactions(page = 1, pageSize = 20, scopeParams = null, filters = null) {
  const params = withScopeParams({ page, page_size: pageSize }, scopeParams);
  if (filters) {
    if (Array.isArray(filters.symbols) && filters.symbols.length > 0) {
      params.set('symbols', filters.symbols.join(','));
    }
    if (filters.date_from) params.set('date_from', filters.date_from);
    if (filters.date_to) params.set('date_to', filters.date_to);
  }
  return fetchWithHandling(`/transactions?${params.toString()}`);
}

export async function fetchTransactionFilterOptions(scopeParams = null) {
  const params = withScopeParams({}, scopeParams);
  // display_currency is irrelevant for filter options; keep payload minimal.
  params.delete('display_currency');
  return fetchWithHandling(`/transactions/filter-options?${params.toString()}`);
}

function _summaryCacheKey(scopeParams, options = {}) {
  const ts =
    options.includeTimeseries === false
      ? 'false'
      : options.includeTimeseries === true
        ? 'true'
        : 'default';
  return `${_scopeKey(scopeParams)}&include_timeseries=${ts}`;
}

export function invalidateDashboardSummaryCache() {
  _dashboardSummaryCacheByScope = new Map();
}

export async function fetchDashboardSummary(scopeParams = null, options = {}) {
  const key = _summaryCacheKey(scopeParams, options);
  if (_dashboardSummaryCacheByScope.has(key)) {
    return _dashboardSummaryCacheByScope.get(key);
  }
  const params = withScopeParams({}, scopeParams);
  if (options.includeTimeseries === false) {
    params.set('include_timeseries', 'false');
  } else if (options.includeTimeseries === true) {
    params.set('include_timeseries', 'true');
  }
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

function _scopeParamsFromMetricSheetParams(params = {}) {
  const { portfolio_id, portfolio_scope, display_currency } = params;
  if (portfolio_id != null) {
    return { portfolio_id, display_currency };
  }
  return {
    portfolio_scope: portfolio_scope ?? 'all',
    display_currency,
  };
}

export function buildMetricSheetQueryParams(params = {}) {
  const {
    portfolio_id,
    portfolio_scope,
    display_currency,
    range = '1Y',
    benchmark,
    folio_number,
    subjects,
    ...rest
  } = params;

  const qs = withScopeParams({ range, ...rest }, _scopeParamsFromMetricSheetParams(params));

  if (benchmark) {
    qs.set('benchmark', benchmark);
  }
  if (folio_number) {
    qs.set('folio_number', folio_number);
  }
  if (subjects) {
    qs.set('subjects', subjects);
  }

  return qs;
}

/** GET /api/v1/analytics/performance-metrics — portfolio Metric Sheet. */
export async function getPortfolioMetricSheet(params = {}) {
  const qs = buildMetricSheetQueryParams(params);
  return fetchWithHandling(`/analytics/performance-metrics?${qs.toString()}`);
}

/** GET /api/v1/analytics/assets/{symbol}/performance-metrics — asset Metric Sheet. */
export async function getAssetMetricSheet(assetSymbol, params = {}) {
  const sym = encodeURIComponent(assetSymbol);
  const qs = buildMetricSheetQueryParams(params);
  return fetchWithHandling(`/analytics/assets/${sym}/performance-metrics?${qs.toString()}`);
}

/** GET /api/v1/analytics/compare — two-asset Metric Sheet comparison. */
export async function getCompareMetricSheet(params = {}) {
  if (!params.subjects) {
    throw new Error('subjects is required for compare Metric Sheet');
  }
  const qs = buildMetricSheetQueryParams(params);
  return fetchWithHandling(`/analytics/compare?${qs.toString()}`);
}
