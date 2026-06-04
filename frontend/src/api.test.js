import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from './api';

const defaultFetchOptions = { credentials: 'include' };

describe('API Service', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    api.invalidateDashboardSummaryCache();
    api.setUnauthorizedHandler(null);
  });

  it('fetchTransactions calls the correct endpoint', async () => {
    const mockResponse = { items: [], total: 0 };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const data = await api.fetchTransactions(1, 20);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/transactions?page=1&page_size=20&portfolio_scope=all&display_currency=EUR',
      expect.objectContaining(defaultFetchOptions)
    );
    expect(data).toEqual(mockResponse);
  });

  it('fetchDashboardSummary calls the correct endpoint', async () => {
    const mockResponse = { total_invested: 15000 };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const data = await api.fetchDashboardSummary({ portfolio_scope: 'all', display_currency: 'INR' });
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/portfolio/summary?portfolio_scope=all&display_currency=INR', expect.objectContaining(defaultFetchOptions));
    expect(data).toEqual(mockResponse);
  });

  it('fetchPortfolioPerformance passes display_currency for value metric', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    await api.fetchPortfolioPerformance('value', null, '1Y', { portfolio_scope: 'all', display_currency: 'INR' });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/portfolio/performance?metric=value&range=1Y&portfolio_scope=all&display_currency=INR',
      expect.objectContaining(defaultFetchOptions)
    );
  });

  it('fetchDashboardSummary calls the correct endpoint with EUR default', async () => {
    const mockResponse = { total_invested: 15000 };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const data = await api.fetchDashboardSummary();
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/portfolio/summary?portfolio_scope=all&display_currency=EUR', expect.objectContaining(defaultFetchOptions));
    expect(data).toEqual(mockResponse);
  });

  it('fetchDashboardSummary with includeTimeseries false appends query param', async () => {
    const mockResponse = { total_invested: 15000, timeseries: [] };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const data = await api.fetchDashboardSummary(
      { portfolio_scope: 'all', display_currency: 'EUR' },
      { includeTimeseries: false }
    );
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('portfolio_scope=all');
    expect(url).toContain('display_currency=EUR');
    expect(url).toContain('include_timeseries=false');
    expect(data).toEqual(mockResponse);
  });

  it('fetchDashboardSummary caches until invalidated', async () => {
    const mockResponse = { total_invested: 15000 };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const a = await api.fetchDashboardSummary();
    const b = await api.fetchDashboardSummary();
    expect(a).toEqual(mockResponse);
    expect(b).toEqual(mockResponse);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    api.invalidateDashboardSummaryCache();
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });
    await api.fetchDashboardSummary();
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('fetchDashboardSummary uses separate cache keys for includeTimeseries false vs default', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ total_invested: 1, label: 'light' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ total_invested: 2, label: 'full' }),
      });

    const light = await api.fetchDashboardSummary(null, { includeTimeseries: false });
    const full = await api.fetchDashboardSummary();
    expect(light.label).toBe('light');
    expect(full.label).toBe('full');
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(global.fetch.mock.calls[0][0]).toContain('include_timeseries=false');
    expect(global.fetch.mock.calls[1][0]).not.toContain('include_timeseries');
  });

  it('fetchHoldings calls the correct endpoint', async () => {
    const mockResponse = { holdings: [] };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const data = await api.fetchHoldings();
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/portfolio/holdings?portfolio_scope=all&display_currency=EUR', expect.objectContaining(defaultFetchOptions));
    expect(data).toEqual(mockResponse);
  });

  it('withScopeParams uses portfolio_id for real portfolio', () => {
    const params = api.withScopeParams({ page: 1 }, { portfolio_id: 2, display_currency: 'USD' });
    expect(params.get('portfolio_id')).toBe('2');
    expect(params.has('portfolio_scope')).toBe(false);
    expect(params.get('display_currency')).toBe('USD');
  });

  it('withScopeParams never sends both portfolio_scope and portfolio_id', () => {
    const params = api.withScopeParams({}, { portfolio_scope: 'all', display_currency: 'EUR' });
    expect(params.get('portfolio_scope')).toBe('all');
    expect(params.has('portfolio_id')).toBe(false);
  });

  it('fetchPortfolioPerformance sends benchmark for return metrics', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ series: [] }) });
    await api.fetchPortfolioPerformance('cumulative_return', '^GSPC', '1Y', {
      portfolio_scope: 'all',
      display_currency: 'EUR',
    });
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('benchmark=%5EGSPC');
    expect(url).toContain('metric=cumulative_return');
    expect(url).toContain('range=1Y');
  });

  it('importTransactionsCsv uses multipart file field', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true, imported_count: 1, errors: [] }),
    });
    const file = new File(['a'], 't.csv', { type: 'text/csv' });
    await api.importTransactionsCsv(file, 1);
    const [, opts] = global.fetch.mock.calls[0];
    expect(opts.method).toBe('POST');
    expect(opts.body).toBeInstanceOf(FormData);
    expect(opts.body.get('file')).toBe(file);
    expect(global.fetch.mock.calls[0][0]).toContain('portfolio_id=1');
  });

  it('throws an error on non-ok response', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: 'Bad request' }),
    });

    await expect(api.fetchDashboardSummary()).rejects.toThrow('Bad request');
  });

  it('getPortfolioMetricSheet calls analytics performance-metrics with scope and range', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ metrics: {} }) });
    await api.getPortfolioMetricSheet({
      portfolio_scope: 'all',
      display_currency: 'EUR',
      range: '3Y',
      benchmark: '^GSPC',
    });
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/analytics/performance-metrics?');
    expect(url).toContain('portfolio_scope=all');
    expect(url).toContain('display_currency=EUR');
    expect(url).toContain('range=3Y');
    expect(url).toContain('benchmark=%5EGSPC');
  });

  it('getAssetMetricSheet encodes symbol and passes folio_number', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ metrics: {} }) });
    await api.getAssetMetricSheet('120503', {
      portfolio_id: 2,
      display_currency: 'INR',
      range: 'ALL',
      folio_number: 'FOLIO-12345',
    });
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/analytics/assets/120503/performance-metrics?');
    expect(url).toContain('portfolio_id=2');
    expect(url).toContain('display_currency=INR');
    expect(url).toContain('range=ALL');
    expect(url).toContain('folio_number=FOLIO-12345');
  });

  it('getCompareMetricSheet calls compare endpoint with subjects', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ subjects: [] }) });
    await api.getCompareMetricSheet({
      portfolio_scope: 'all',
      display_currency: 'EUR',
      range: '1Y',
      subjects: 'asset:AAPL,asset:MSFT',
    });
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/analytics/compare?');
    expect(url).toContain('subjects=asset%3AAAPL%2Casset%3AMSFT');
    expect(url).toContain('range=1Y');
  });

  it('getCompareMetricSheet requires subjects', async () => {
    await expect(api.getCompareMetricSheet({ range: '1Y' })).rejects.toThrow('subjects is required');
  });
});
