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

  it('fetchCashBalances calls balances endpoint with portfolio scope', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ portfolio_scope: 'all', balances: [], totals_by_currency: [] }),
    });
    await api.fetchCashBalances({ portfolio_scope: 'all', display_currency: 'EUR' });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/cash/balances?portfolio_scope=all',
      expect.objectContaining(defaultFetchOptions)
    );
  });

  it('fetchCashBalances passes portfolio_id and filters without display_currency', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ balances: [] }),
    });
    await api.fetchCashBalances({
      portfolio_id: 2,
      display_currency: 'INR',
      as_of_date: '2026-06-01',
      currency: 'EUR',
    });
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/cash/balances?');
    expect(url).toContain('portfolio_id=2');
    expect(url).not.toContain('display_currency');
    expect(url).toContain('as_of_date=2026-06-01');
    expect(url).toContain('currency=EUR');
  });

  it('fetchCashLedger calls ledger endpoint with pagination and filters', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, page_size: 20, pages: 0 }),
    });
    await api.fetchCashLedger({
      portfolio_scope: 'all',
      display_currency: 'EUR',
      page: 2,
      page_size: 50,
      entry_type: 'CASH_DEPOSIT',
      date_from: '2026-01-01',
      date_to: '2026-06-01',
    });
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/cash/ledger?');
    expect(url).toContain('portfolio_scope=all');
    expect(url).toContain('page=2');
    expect(url).toContain('page_size=50');
    expect(url).toContain('entry_type=CASH_DEPOSIT');
    expect(url).toContain('date_from=2026-01-01');
    expect(url).toContain('date_to=2026-06-01');
    expect(url).not.toContain('display_currency');
  });

  it('createCashDeposit posts JSON payload and returns parsed body', async () => {
    const responseBody = { id: 1, entry_type: 'CASH_DEPOSIT', amount: 1000 };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => responseBody,
    });
    const payload = {
      portfolio_id: 1,
      date: '2026-06-04',
      currency: 'EUR',
      amount: 1000,
      source_of_funds: 'Bank',
      note: 'Test',
    };
    const result = await api.createCashDeposit(payload);
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/cash/deposits');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual(payload);
    expect(result).toEqual(responseBody);
  });

  it('createCashDeposit reads response body only once on success', async () => {
    let jsonCalls = 0;
    const responseBody = { id: 42, entry_type: 'CASH_DEPOSIT', amount: 250 };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => {
        jsonCalls += 1;
        if (jsonCalls > 1) {
          throw new TypeError("Failed to execute 'json' on 'Response': body stream already read");
        }
        return responseBody;
      },
    });

    const result = await api.createCashDeposit({
      portfolio_id: 1,
      date: '2026-06-04',
      currency: 'EUR',
      amount: 250,
    });

    expect(jsonCalls).toBe(1);
    expect(result).toEqual(responseBody);
  });

  it('createCashDeposit parses validation error once', async () => {
    let jsonCalls = 0;
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => {
        jsonCalls += 1;
        if (jsonCalls > 1) {
          throw new TypeError("Failed to execute 'json' on 'Response': body stream already read");
        }
        return { amount: ['amount must be positive'] };
      },
    });

    await expect(
      api.createCashDeposit({
        portfolio_id: 1,
        date: '2026-06-04',
        currency: 'EUR',
        amount: 0,
      })
    ).rejects.toMatchObject({
      name: 'CashApiError',
      message: 'amount: amount must be positive',
    });
    expect(jsonCalls).toBe(1);
  });

  it('createCashWithdrawal reads error body only once', async () => {
    let jsonCalls = 0;
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => {
        jsonCalls += 1;
        if (jsonCalls > 1) {
          throw new TypeError("Failed to execute 'json' on 'Response': body stream already read");
        }
        return {
          detail: 'Insufficient cash balance for withdrawal.',
          required: 500,
          available: 100,
          shortfall: 400,
          currency: 'EUR',
        };
      },
    });

    await expect(
      api.createCashWithdrawal({
        portfolio_id: 1,
        date: '2026-06-04',
        currency: 'EUR',
        amount: 500,
      })
    ).rejects.toMatchObject({
      name: 'CashApiError',
      required: 500,
      available: 100,
      shortfall: 400,
      currency: 'EUR',
    });
    expect(jsonCalls).toBe(1);
  });

  it('createCashWithdrawal throws CashApiError with shortfall fields', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({
        detail: 'Insufficient cash balance for withdrawal.',
        required: 500,
        available: 100,
        shortfall: 400,
        currency: 'EUR',
      }),
    });
    await expect(
      api.createCashWithdrawal({
        portfolio_id: 1,
        date: '2026-06-04',
        currency: 'EUR',
        amount: 500,
      })
    ).rejects.toMatchObject({
      name: 'CashApiError',
      message: 'Insufficient cash balance for withdrawal.',
      required: 500,
      available: 100,
      shortfall: 400,
      currency: 'EUR',
    });
  });

  it('updateCashLedgerEntry sends PUT with parsed response', async () => {
    const responseBody = { id: 5, entry_type: 'CASH_DEPOSIT', amount: 900 };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => responseBody,
    });
    const result = await api.updateCashLedgerEntry(5, {
      date: '2026-06-02',
      currency: 'EUR',
      amount: 900,
    });
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/cash/ledger/5');
    expect(opts.method).toBe('PUT');
    expect(result).toEqual(responseBody);
  });

  it('deleteCashLedgerEntry returns null on 204 without double json read', async () => {
    let jsonCalls = 0;
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: async () => {
        jsonCalls += 1;
        throw new TypeError("Failed to execute 'json' on 'Response': body stream already read");
      },
    });
    const result = await api.deleteCashLedgerEntry(9);
    expect(result).toBeNull();
    expect(jsonCalls).toBe(0);
  });

  it('updateCashLedgerEntry surfaces future impact fields', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({
        detail: 'This cash change would make future cash balance negative.',
        currency: 'EUR',
        earliest_negative_date: '2026-06-05',
        lowest_balance: -500,
        affected_entries: [
          {
            id: 2,
            date: '2026-06-05',
            entry_type: 'BUY_SETTLEMENT',
            amount: -1000,
            linked_transaction_id: 99,
            asset_symbol: 'AAPL',
          },
        ],
      }),
    });
    await expect(
      api.updateCashLedgerEntry(1, {
        date: '2026-06-01',
        currency: 'EUR',
        amount: 1,
      })
    ).rejects.toMatchObject({
      name: 'CashApiError',
      earliest_negative_date: '2026-06-05',
      lowest_balance: -500,
      affected_entries: expect.any(Array),
    });
  });

  it('deleteCashLedgerEntry reads error body only once on future impact', async () => {
    let jsonCalls = 0;
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => {
        jsonCalls += 1;
        if (jsonCalls > 1) {
          throw new TypeError("Failed to execute 'json' on 'Response': body stream already read");
        }
        return {
          detail: 'This cash change would make future cash balance negative.',
          currency: 'EUR',
          earliest_negative_date: '2026-06-10',
          lowest_balance: -100,
          affected_entries: [],
        };
      },
    });
    await expect(api.deleteCashLedgerEntry(3)).rejects.toMatchObject({
      name: 'CashApiError',
      earliest_negative_date: '2026-06-10',
    });
    expect(jsonCalls).toBe(1);
  });

  it('withCashScopeParams never sends display_currency', () => {
    const params = api.withCashScopeParams({ currency: 'EUR' }, { portfolio_scope: 'all' });
    expect(params.get('portfolio_scope')).toBe('all');
    expect(params.has('display_currency')).toBe(false);
    expect(params.get('currency')).toBe('EUR');
  });

  it('createTransaction reads error body only once', async () => {
    let jsonCalls = 0;
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => {
        jsonCalls += 1;
        if (jsonCalls > 1) {
          throw new TypeError("Failed to execute 'json' on 'Response': body stream already read");
        }
        return {
          detail: 'Insufficient cash balance for purchase.',
          required: 1005,
          available: 500,
          shortfall: 505,
          currency: 'EUR',
        };
      },
    });

    await expect(
      api.createTransaction({
        asset_symbol: 'AAPL',
        date: '2026-06-04',
        type: 'BUY',
        quantity: 10,
        price_per_share: 100,
        currency: 'EUR',
        portfolio_id: 1,
      })
    ).rejects.toMatchObject({
      name: 'TransactionApiError',
      required: 1005,
      available: 500,
      shortfall: 505,
      currency: 'EUR',
    });
    expect(jsonCalls).toBe(1);
  });

  it('createTransaction throws TransactionApiError with shortfall fields', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({
        detail: 'Insufficient cash balance for purchase.',
        required: 1005,
        available: 500,
        shortfall: 505,
        currency: 'EUR',
      }),
    });
    await expect(
      api.createTransaction({
        asset_symbol: 'AAPL',
        date: '2026-06-04',
        type: 'BUY',
        quantity: 10,
        price_per_share: 100,
        currency: 'EUR',
        portfolio_id: 1,
      })
    ).rejects.toMatchObject({
      name: 'TransactionApiError',
      message: 'Insufficient cash balance for purchase.',
      required: 1005,
      available: 500,
      shortfall: 505,
      currency: 'EUR',
    });
  });

  it('createTransaction surfaces field validation errors', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({
        asset_symbol: ['This field is required.'],
      }),
    });
    await expect(
      api.createTransaction({
        date: '2026-06-04',
        type: 'BUY',
        quantity: 1,
        price_per_share: 10,
        currency: 'EUR',
      })
    ).rejects.toMatchObject({
      name: 'TransactionApiError',
      message: 'asset_symbol: This field is required.',
      fieldErrors: { asset_symbol: ['This field is required.'] },
    });
  });
});

describe('cash backfill API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('previewCashBackfill posts payload and parses body once', async () => {
    let jsonCalls = 0;
    const body = { proposed_deposits: [], summary: { proposed_deposit_count: 0 } };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => {
        jsonCalls += 1;
        return body;
      },
    });

    const result = await api.previewCashBackfill({
      portfolio_id: 1,
      start_date: '2022-05-01',
      end_date: '2026-06-04',
      mode: 'shortfall',
    });

    expect(jsonCalls).toBe(1);
    expect(result).toEqual(body);
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/cash/backfill-preview');
    expect(JSON.parse(opts.body)).toEqual({
      portfolio_id: 1,
      start_date: '2022-05-01',
      end_date: '2026-06-04',
      mode: 'shortfall',
    });
  });

  it('applyCashBackfill always sends confirmed true', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ created_count: 0, skipped_existing_count: 0 }),
    });

    await api.applyCashBackfill({ portfolio_id: 2, mode: 'shortfall' });

    const [, opts] = global.fetch.mock.calls[0];
    expect(JSON.parse(opts.body)).toEqual({
      portfolio_id: 2,
      mode: 'shortfall',
      confirmed: true,
    });
  });

  it('applyCashBackfill surfaces blocking warnings from error body', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({
        detail: 'Backfill apply blocked.',
        blocking_warnings: ['BLOCKING: test'],
      }),
    });

    await expect(api.applyCashBackfill({ portfolio_id: 1 })).rejects.toMatchObject({
      name: 'CashApiError',
      blocking_warnings: ['BLOCKING: test'],
    });
  });
});
