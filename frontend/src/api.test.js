import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from './api';

describe('API Service', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    api.invalidateDashboardSummaryCache();
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
      {}
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
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/portfolio/summary?portfolio_scope=all&display_currency=INR', {});
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
      {}
    );
  });

  it('fetchDashboardSummary calls the correct endpoint with EUR default', async () => {
    const mockResponse = { total_invested: 15000 };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const data = await api.fetchDashboardSummary();
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/portfolio/summary?portfolio_scope=all&display_currency=EUR', {});
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

  it('fetchHoldings calls the correct endpoint', async () => {
    const mockResponse = { holdings: [] };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const data = await api.fetchHoldings();
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/portfolio/holdings?portfolio_scope=all&display_currency=EUR', {});
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
});
