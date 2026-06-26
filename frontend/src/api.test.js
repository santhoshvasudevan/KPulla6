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

  it('fetchTransactionFilterOptions scopes by portfolio without display_currency', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ portfolios: [], symbols: [] }),
    });

    await api.fetchTransactionFilterOptions({ portfolio_id: 2, display_currency: 'INR' });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/transactions/filter-options?portfolio_id=2',
      expect.objectContaining(defaultFetchOptions)
    );
  });

  it('fetchTransactionFilterOptions keeps all-portfolio scope without display_currency', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ portfolios: [], symbols: [] }),
    });

    await api.fetchTransactionFilterOptions({ portfolio_scope: 'all', display_currency: 'USD' });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/transactions/filter-options?portfolio_scope=all',
      expect.objectContaining(defaultFetchOptions)
    );
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

  it('fetchBankAccounts calls the correct endpoint', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => [] });
    await api.fetchBankAccounts();
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/bank-accounts', expect.objectContaining(defaultFetchOptions));
  });

  it('fetchBankAccounts calls the correct endpoint', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => [] });
    await api.fetchBankAccounts();
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/bank-accounts', expect.objectContaining(defaultFetchOptions));
  });

  it('fetchBankAccountBalance calls balance endpoint with as_of', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ current_balance: 100, balance_as_of_date: 0, as_of_date: '2023-09-23' }),
    });
    await api.fetchBankAccountBalance(5, { as_of: '2023-09-23' });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/bank-accounts/5/balance?as_of=2023-09-23',
      expect.objectContaining(defaultFetchOptions)
    );
  });

  it('createFixedDeposit throws FixedDepositApiError with structured balance fields', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({
        detail: 'Insufficient bank account balance for this movement.',
        required: 1109389,
        available: 0,
        available_as_of_date: 0,
        current_balance: 1109389,
        shortfall: 1109389,
        currency: 'INR',
        investment_date: '2023-09-23',
        hint: 'Current ledger balance is higher because cash movements exist after the FD investment date.',
      }),
    });
    await expect(
      api.createFixedDeposit({ portfolio_id: 1, bank_account_id: 2, principal_amount: '1109389' })
    ).rejects.toMatchObject({
      name: 'FixedDepositApiError',
      available_as_of_date: 0,
      current_balance: 1109389,
      investment_date: '2023-09-23',
    });
  });

  it('fetchCashMovements calls the correct endpoint with bank_account_id filter', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ items: [], total: 0 }) });
    await api.fetchCashMovements({ bank_account_id: 3, page: 1, page_size: 20 });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/cash-movements?bank_account_id=3&page=1&page_size=20',
      expect.objectContaining(defaultFetchOptions)
    );
  });

  it('createCashMovement posts to cash-movements', async () => {
    const payload = {
      bank_account_id: 1,
      movement_type: 'MANUAL_DEPOSIT',
      amount: '100.00',
      movement_date: '2026-06-01',
    };
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ id: 1, ...payload }) });
    await api.createCashMovement(payload);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/cash-movements',
      expect.objectContaining({
        ...defaultFetchOptions,
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
  });

  it('fetchFixedDeposits calls the correct endpoint with portfolio scope', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => [] });
    await api.fetchFixedDeposits({ portfolio_id: 2, display_currency: 'INR' });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/fixed-deposits?portfolio_id=2',
      expect.objectContaining(defaultFetchOptions)
    );
  });

  it('fetchFixedDepositInterestPayments calls nested FD endpoint', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => [] });
    await api.fetchFixedDepositInterestPayments(7);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/fixed-deposits/7/interest-payments',
      expect.objectContaining(defaultFetchOptions)
    );
  });

  it('fetchFixedDepositInterestReport calls report endpoint with filters', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ rows: [], totals: { row_count: 0 } }),
    });
    await api.fetchFixedDepositInterestReport({
      portfolio_scope: 'all',
      display_currency: 'INR',
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      group_by: 'year',
    });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/reports/fixed-deposit-interest?portfolio_scope=all&display_currency=INR&start_date=2024-01-01&end_date=2024-12-31&group_by=year',
      expect.objectContaining(defaultFetchOptions)
    );
  });

  it('exportFixedDepositInterestReportCsv fetches CSV blob without group_by', async () => {
    const blob = new Blob(['date,source'], { type: 'text/csv' });
    global.fetch.mockResolvedValueOnce({
      ok: true,
      blob: async () => blob,
      headers: {
        get: (name) =>
          name.toLowerCase() === 'content-disposition'
            ? 'attachment; filename="fd-interest-tax-2024-01-01-to-2024-12-31.csv"'
            : null,
      },
    });
    const result = await api.exportFixedDepositInterestReportCsv({
      portfolio_scope: 'all',
      display_currency: 'INR',
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      group_by: 'year',
    });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/reports/fixed-deposit-interest/export.csv?portfolio_scope=all&display_currency=INR&start_date=2024-01-01&end_date=2024-12-31',
      expect.objectContaining(defaultFetchOptions)
    );
    expect(result.filename).toBe('fd-interest-tax-2024-01-01-to-2024-12-31.csv');
    expect(result.blob).toBe(blob);
  });

  it('createFixedDepositInterestPayment posts to nested FD endpoint', async () => {
    const payload = {
      payment_date: '2024-04-01',
      gross_interest: '1000',
      tax_withheld: '100',
    };
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ id: 1, ...payload }) });
    await api.createFixedDepositInterestPayment(7, payload);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/fixed-deposits/7/interest-payments',
      expect.objectContaining({
        ...defaultFetchOptions,
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
  });

  it('reverseCashMovement posts to reverse endpoint', async () => {
    const payload = { reversal_date: '2026-06-10', reason: 'Duplicate' };
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ message: 'ok' }) });
    await api.reverseCashMovement(5, payload);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/cash-movements/5/reverse',
      expect.objectContaining({
        ...defaultFetchOptions,
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
  });

  it('reverseFixedDepositInterestPayment posts to reverse endpoint', async () => {
    const payload = { reversal_date: '2024-04-15', reason: 'Wrong amount' };
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ message: 'ok' }) });
    await api.reverseFixedDepositInterestPayment(9, payload);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/fixed-deposit-interest-payments/9/reverse',
      expect.objectContaining({
        ...defaultFetchOptions,
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
  });

  it('markFixedDepositMatured posts to mark-matured endpoint', async () => {
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ id: 7, status: 'MATURED' }) });
    await api.markFixedDepositMatured(7);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/fixed-deposits/7/mark-matured',
      expect.objectContaining({ ...defaultFetchOptions, method: 'POST' })
    );
  });

  it('settleFixedDeposit posts to settle endpoint', async () => {
    const payload = {
      settlement_type: 'MATURITY',
      settlement_date: '2026-01-01',
      principal_returned: '100000',
      gross_interest: '5000',
      tax_withheld: '500',
    };
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ id: 1, ...payload }) });
    await api.settleFixedDeposit(7, payload);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/fixed-deposits/7/settle',
      expect.objectContaining({
        ...defaultFetchOptions,
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
  });

  it('renewFixedDeposit posts to renew endpoint', async () => {
    const payload = {
      renewal_date: '2026-01-01',
      new_deposit_account_number: 'FD-002',
      new_principal_amount: '100000',
      new_interest_rate_percent: '7.5',
      new_interest_payout_frequency: 'QUARTERLY',
      new_investment_date: '2026-01-01',
      new_maturity_date: '2028-01-01',
      cash_payout_amount: '0',
    };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ renewal_id: 1, old_fixed_deposit: { id: 7, status: 'MATURED_SETTLED' } }),
    });
    await api.renewFixedDeposit(7, payload);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/fixed-deposits/7/renew',
      expect.objectContaining({
        ...defaultFetchOptions,
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
  });

  it('cancelFixedDeposit posts to cancel endpoint', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 7, status: 'CANCELLED', is_active: false }),
    });
    await api.cancelFixedDeposit(7, { cancellation_date: '2024-06-15' });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/fixed-deposits/7/cancel',
      expect.objectContaining({
        ...defaultFetchOptions,
        method: 'POST',
        body: JSON.stringify({ cancellation_date: '2024-06-15' }),
      })
    );
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

  it('importTransactionsCsv sends cash preview confirmation flags only when confirmed', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true, imported_count: 1, errors: [] }),
    });
    const file = new File(['a'], 'cash-aware.csv', { type: 'text/csv' });

    await api.importTransactionsCsv(file, 2, {
      createCashDeposits: true,
      cashPreviewConfirmed: true,
    });

    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/transactions/import-csv?');
    expect(url).toContain('portfolio_id=2');
    expect(url).toContain('create_cash_deposits=true');
    expect(url).toContain('cash_preview_confirmed=true');
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

  it('fetchCashOverview calls overview endpoint with scope and display params', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ rows: [], totals: {}, warnings: [] }),
    });
    await api.fetchCashOverview({
      portfolio_scope: 'all',
      display_currency: 'EUR',
      include_unassigned: true,
    });
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/cash/overview?');
    expect(url).toContain('portfolio_scope=all');
    expect(url).toContain('display_currency=EUR');
    expect(url).toContain('include_unassigned=true');
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

  it('createCashTransfer posts JSON payload to transfers endpoint', async () => {
    const responseBody = {
      transfer_group_id: 10,
      date: '2026-06-06',
      source_currency: 'USD',
      source_amount: 1000,
      target_currency: 'EUR',
      target_amount: 920,
      implied_rate: 0.92,
      source_portfolio_id: 1,
      target_portfolio_id: 2,
      entries: [],
    };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => responseBody,
    });
    const payload = {
      source_portfolio_id: 1,
      target_portfolio_id: 2,
      date: '2026-06-06',
      source_currency: 'USD',
      source_amount: 1000,
      target_currency: 'EUR',
      target_amount: 920,
      note: 'Broker conversion',
    };
    const result = await api.createCashTransfer(payload);
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/cash/transfers');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual(payload);
    expect(result).toEqual(responseBody);
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

  it('reverseCashLedgerEntry posts reversal payload', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({
        original: { id: 103, is_reversed: true },
        reversal: { id: 201, entry_type: 'CASH_WITHDRAWAL', amount: -1109389 },
        message: 'Broker cash entry reversed.',
      }),
    });
    await api.reverseCashLedgerEntry(103, {
      reversal_date: '2026-06-26',
      reason: 'Recorded in broker ledger by mistake',
    });
    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toContain('/api/v1/cash/ledger/103/reverse');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({
      reversal_date: '2026-06-26',
      reason: 'Recorded in broker ledger by mistake',
    });
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

  it('deleteTransaction throws TransactionApiError with future-impact fields', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({
        detail: 'This transaction change would make future cash balance negative.',
        currency: 'EUR',
        earliest_negative_date: '2026-06-10',
        lowest_balance: -500,
        affected_entries: [
          {
            id: 12,
            date: '2026-06-10',
            entry_type: 'BUY_SETTLEMENT',
            amount: -1500,
            linked_transaction_id: 8,
            asset_symbol: 'AAPL',
          },
        ],
      }),
    });
    await expect(api.deleteTransaction(5)).rejects.toMatchObject({
      name: 'TransactionApiError',
      currency: 'EUR',
      earliest_negative_date: '2026-06-10',
      lowest_balance: -500,
      affected_entries: expect.any(Array),
    });
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

  it('previewCashBulkEntries posts schedule payload', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ entry_count: 1, entries: [] }),
    });
    await api.previewCashBulkEntries({
      portfolio_id: 1,
      entry_type: 'CASH_DEPOSIT',
      currency: 'EUR',
      amount: 900,
      start_date: '2022-06-01',
      end_date: '2022-12-01',
      frequency: 'monthly',
    });
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/cash/bulk-entries/preview');
    expect(JSON.parse(opts.body)).toEqual({
      portfolio_id: 1,
      entry_type: 'CASH_DEPOSIT',
      currency: 'EUR',
      amount: 900,
      start_date: '2022-06-01',
      end_date: '2022-12-01',
      frequency: 'monthly',
      source_of_funds: '',
      note: '',
    });
  });

  it('applyCashBulkEntries always sends confirmed true', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ created_count: 0 }),
    });
    await api.applyCashBulkEntries({
      portfolio_id: 1,
      entry_type: 'CASH_DEPOSIT',
      currency: 'EUR',
      amount: 900,
      start_date: '2022-06-01',
      frequency: 'once',
    });
    const [, opts] = global.fetch.mock.calls[0];
    expect(JSON.parse(opts.body).confirmed).toBe(true);
  });

  it('previewCashBulkEntries surfaces CashApiError from backend', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'End date is required for monthly frequency.' }),
    });
    await expect(
      api.previewCashBulkEntries({
        portfolio_id: 1,
        entry_type: 'CASH_DEPOSIT',
        currency: 'EUR',
        amount: 900,
        start_date: '2022-06-01',
        frequency: 'monthly',
      })
    ).rejects.toMatchObject({
      name: 'CashApiError',
      message: 'End date is required for monthly frequency.',
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
