const API_ROOT = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const BASE_URL = `${API_ROOT}/api/v1`;

let _dashboardSummaryCacheByScope = new Map();
let _onUnauthorized = null;

export function setUnauthorizedHandler(handler) {
  _onUnauthorized = handler;
}

function getCookie(name) {
  if (typeof document === 'undefined') return '';
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : '';
}

function defaultFetchOptions(options = {}) {
  const headers = new Headers(options.headers || {});
  const method = (options.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    const csrf = getCookie('csrftoken');
    if (csrf) headers.set('X-CSRFToken', csrf);
  }
  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  return {
    credentials: 'include',
    ...options,
    headers,
  };
}

function buildUrl(path, params) {
  const qs = params ? `?${params.toString()}` : '';
  return `${BASE_URL}${path}${qs}`;
}

export async function fetchWithHandling(path, options = {}) {
  const response = await fetch(buildUrl(path), defaultFetchOptions(options));
  if (response.status === 401 && !path.startsWith('/auth/') && _onUnauthorized) {
    _onUnauthorized();
  }
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

export async function ensureCsrfCookie() {
  return fetchWithHandling('/auth/csrf');
}

export async function fetchCurrentUser() {
  return fetchWithHandling('/auth/me');
}

export async function login(usernameOrEmail, password) {
  return fetchWithHandling('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username_or_email: usernameOrEmail, password }),
  });
}

export async function logout() {
  return fetchWithHandling('/auth/logout', { method: 'POST' });
}

export async function register(payload) {
  return fetchWithHandling('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function requestPasswordReset(email) {
  return fetchWithHandling('/auth/password-reset', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
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

const RESERVED_API_ERROR_KEYS = [
  'detail',
  'message',
  'required',
  'available',
  'shortfall',
  'currency',
  'earliest_negative_date',
  'lowest_balance',
  'affected_entries',
];

function extractFieldErrors(errorData) {
  if (!errorData || typeof errorData !== 'object') return {};
  return Object.fromEntries(
    Object.entries(errorData).filter(([key]) => !RESERVED_API_ERROR_KEYS.includes(key))
  );
}

function buildApiErrorMessage(errorData, status) {
  if (!errorData || typeof errorData !== 'object') {
    return `Request failed (${status})`;
  }
  const detail = errorData.detail;
  let message =
    typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
        : errorData.message || '';
  if (!message && typeof errorData === 'object') {
    const fieldMsgs = Object.entries(errorData)
      .filter(([key]) => !RESERVED_API_ERROR_KEYS.includes(key))
      .map(([key, val]) => {
        const text = Array.isArray(val) ? val.join(', ') : String(val);
        return `${key}: ${text}`;
      });
    if (fieldMsgs.length) message = fieldMsgs.join('; ');
  }
  if (!message) message = `Request failed (${status})`;
  return message;
}

/** Structured API errors (detail, shortfall fields, field validation). */
export class ApiError extends Error {
  constructor(message, extras = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = extras.status;
    this.detail = extras.detail;
    this.required = extras.required;
    this.available = extras.available;
    this.shortfall = extras.shortfall;
    this.currency = extras.currency;
    this.data = extras.data ?? null;
    this.fieldErrors = extras.fieldErrors ?? extractFieldErrors(this.data ?? {});
    this.earliest_negative_date = extras.earliest_negative_date;
    this.lowest_balance = extras.lowest_balance;
    this.affected_entries = extras.affected_entries ?? null;
  }
}

/** Transaction write errors may include insufficient-cash fields from the backend. */
export class TransactionApiError extends ApiError {
  constructor(message, extras = {}) {
    super(message, extras);
    this.name = 'TransactionApiError';
  }
}

async function transactionRequestWithHandling(path, { method = 'POST', body } = {}) {
  const hasJsonBody = body != null && method !== 'GET' && method !== 'DELETE';
  const response = await fetch(
    buildUrl(path),
    defaultFetchOptions({
      method,
      headers: hasJsonBody ? { 'Content-Type': 'application/json' } : undefined,
      body: hasJsonBody ? JSON.stringify(body) : undefined,
    })
  );
  if (response.status === 401 && !path.startsWith('/auth/') && _onUnauthorized) {
    _onUnauthorized();
  }

  const payload =
    response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    const errorData = payload && typeof payload === 'object' ? payload : {};
    throw new TransactionApiError(buildApiErrorMessage(errorData, response.status), {
      status: response.status,
      detail: errorData.detail,
      required: errorData.required,
      available: errorData.available,
      shortfall: errorData.shortfall,
      currency: errorData.currency,
      data: errorData,
    });
  }
  return payload;
}

export async function createTransaction(data) {
  const res = await transactionRequestWithHandling('/transactions', { method: 'POST', body: data });
  invalidateDashboardSummaryCache();
  return res;
}

export async function updateTransaction(id, data) {
  const res = await transactionRequestWithHandling(`/transactions/${id}`, { method: 'PUT', body: data });
  invalidateDashboardSummaryCache();
  return res;
}

export async function deleteTransaction(id) {
  const res = await fetchWithHandling(`/transactions/${id}`, { method: 'DELETE' });
  invalidateDashboardSummaryCache();
  return res;
}

function _csvImportQuery(portfolioId, options = {}) {
  const params = new URLSearchParams();
  if (portfolioId != null) {
    params.set('portfolio_id', String(portfolioId));
  }
  if (options.createCashDeposits) {
    params.set('create_cash_deposits', 'true');
  }
  if (options.cashPreviewConfirmed) {
    params.set('cash_preview_confirmed', 'true');
  }
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export async function previewCsvImportCash(file, portfolioId = null) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(
    buildUrl(`/transactions/import-csv/preview-cash${_csvImportQuery(portfolioId)}`),
    defaultFetchOptions({
      method: 'POST',
      body: formData,
    })
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.message || 'Cash preview failed');
  }
  return data;
}

export async function importTransactionsCsv(file, portfolioId = null, options = {}) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(
    buildUrl(`/transactions/import-csv${_csvImportQuery(portfolioId, options)}`),
    defaultFetchOptions({
      method: 'POST',
      body: formData,
    })
  );
  const data = await response.json().catch(() => ({}));
  if (response.status === 409) {
    const err = new Error(data.detail || 'CSV import requires cash deposit confirmation');
    err.code = 'csv_cash_preview_required';
    err.preview = data;
    throw err;
  }
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

/** Cash API errors may include insufficient-cash fields from the backend. */
export class CashApiError extends ApiError {
  constructor(message, extras = {}) {
    super(message, extras);
    this.name = 'CashApiError';
    this.row_errors = extras.row_errors ?? null;
    this.blocking_warnings = extras.blocking_warnings ?? null;
  }
}

export function withCashScopeParams(params, scopeParams) {
  const out = new URLSearchParams(params || {});
  if (scopeParams?.portfolio_id != null) {
    out.set('portfolio_id', String(scopeParams.portfolio_id));
  } else {
    out.set('portfolio_scope', scopeParams?.portfolio_scope ?? 'all');
  }
  return out;
}

function cashScopeFromPortfolioContext(scopeParams) {
  if (!scopeParams) return null;
  if (scopeParams.portfolio_id != null) {
    return { portfolio_id: scopeParams.portfolio_id };
  }
  return { portfolio_scope: scopeParams.portfolio_scope ?? 'all' };
}

function appendCashQueryParams(qs, extra = {}) {
  if (extra.as_of_date) qs.set('as_of_date', extra.as_of_date);
  if (extra.currency) qs.set('currency', extra.currency);
  if (extra.entry_type) qs.set('entry_type', extra.entry_type);
  if (extra.date_from) qs.set('date_from', extra.date_from);
  if (extra.date_to) qs.set('date_to', extra.date_to);
  if (extra.page != null) qs.set('page', String(extra.page));
  if (extra.page_size != null) qs.set('page_size', String(extra.page_size));
  return qs;
}


async function cashRequestWithHandling(path, { method = 'POST', body } = {}) {
  const hasJsonBody = body != null && method !== 'GET' && method !== 'DELETE';
  const response = await fetch(
    buildUrl(path),
    defaultFetchOptions({
      method,
      headers: hasJsonBody ? { 'Content-Type': 'application/json' } : undefined,
      body: hasJsonBody ? JSON.stringify(body) : undefined,
    })
  );
  if (response.status === 401 && !path.startsWith('/auth/') && _onUnauthorized) {
    _onUnauthorized();
  }

  const payload =
    response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    const errorData = payload && typeof payload === 'object' ? payload : {};
    throw new CashApiError(buildApiErrorMessage(errorData, response.status), {
      status: response.status,
      detail: errorData.detail,
      required: errorData.required,
      available: errorData.available,
      shortfall: errorData.shortfall,
      currency: errorData.currency,
      earliest_negative_date: errorData.earliest_negative_date,
      lowest_balance: errorData.lowest_balance,
      affected_entries: errorData.affected_entries,
      row_errors: errorData.row_errors,
      blocking_warnings: errorData.blocking_warnings,
      data: errorData,
    });
  }
  return payload;
}

async function postCashWithHandling(path, body) {
  return cashRequestWithHandling(path, { method: 'POST', body });
}

/** GET /api/v1/cash/balances — native balances; no display-currency conversion. */
export async function fetchCashBalances(params = {}) {
  const {
    portfolio_scope,
    portfolio_id,
    as_of_date,
    currency,
    display_currency: _displayCurrency,
    ...rest
  } = params;
  const scope = cashScopeFromPortfolioContext({ portfolio_scope, portfolio_id });
  const qs = appendCashQueryParams(withCashScopeParams(rest, scope), {
    as_of_date,
    currency,
  });
  return fetchWithHandling(`/cash/balances?${qs.toString()}`);
}

/** GET /api/v1/cash/ledger — paginated ledger entries. */
export async function fetchCashLedger(params = {}) {
  const {
    portfolio_scope,
    portfolio_id,
    currency,
    entry_type,
    date_from,
    date_to,
    page = 1,
    page_size = 20,
    display_currency: _displayCurrency,
    ...rest
  } = params;
  const scope = cashScopeFromPortfolioContext({ portfolio_scope, portfolio_id });
  const qs = appendCashQueryParams(withCashScopeParams(rest, scope), {
    currency,
    entry_type,
    date_from,
    date_to,
    page,
    page_size,
  });
  return fetchWithHandling(`/cash/ledger?${qs.toString()}`);
}

/** POST /api/v1/cash/deposits */
export async function createCashDeposit(payload) {
  return postCashWithHandling('/cash/deposits', payload);
}

/** POST /api/v1/cash/withdrawals */
export async function createCashWithdrawal(payload) {
  return postCashWithHandling('/cash/withdrawals', payload);
}

/** PUT /api/v1/cash/ledger/{id} — manual deposit/withdrawal only. */
export async function updateCashLedgerEntry(id, payload) {
  return cashRequestWithHandling(`/cash/ledger/${id}`, { method: 'PUT', body: payload });
}

/** DELETE /api/v1/cash/ledger/{id} — manual deposit/withdrawal only. */
export async function deleteCashLedgerEntry(id) {
  return cashRequestWithHandling(`/cash/ledger/${id}`, { method: 'DELETE' });
}

function buildCashBackfillRequestBody(payload = {}) {
  const body = {
    portfolio_id: payload.portfolio_id,
    mode: payload.mode || 'shortfall',
  };
  if (payload.start_date) body.start_date = payload.start_date;
  if (payload.end_date) body.end_date = payload.end_date;
  return body;
}

/** POST /api/v1/cash/backfill-preview — read-only legacy cash backfill simulation. */
export async function previewCashBackfill(payload) {
  return postCashWithHandling('/cash/backfill-preview', buildCashBackfillRequestBody(payload));
}

/** POST /api/v1/cash/backfill-apply — confirmed; server recomputes preview before writes. */
export async function applyCashBackfill(payload) {
  return postCashWithHandling('/cash/backfill-apply', {
    ...buildCashBackfillRequestBody(payload),
    confirmed: true,
  });
}
