import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import TransactionModal from './TransactionModal';
import * as api from '../api';
import { CashApiError, TransactionApiError } from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    createTransaction: vi.fn(),
    updateTransaction: vi.fn(),
    getCachedMutualFundNav: vi.fn(),
    fetchMissingMutualFundNav: vi.fn(),
    previewProvisionalMutualFundNav: vi.fn(),
    createCashDeposit: vi.fn(),
    createCashWithdrawal: vi.fn(),
    fetchPortfolios: vi.fn(),
  };
});

beforeEach(() => {
  api.getCachedMutualFundNav.mockReset().mockImplementation(async (schemeCode, navDate) => ({
    scheme_code: schemeCode, nav_date: navDate, nav: '42.5000', status: 'available',
  }));
});

describe('TransactionModal record type selector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderModal = ({ initialData = null, selection = null } = {}) =>
    render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
          { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
        ]}
        initialSelection={selection}
        disableFetch
      >
        <TransactionModal
          isOpen
          onClose={vi.fn()}
          onSuccess={vi.fn()}
          initialData={initialData}
        />
      </PortfolioProvider>
    );

  it('shows Record type selector with Cash, Stock, and Mutual Fund', () => {
    renderModal();
    const sel = screen.getByLabelText('record type');
    expect(sel).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Cash' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Stock' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Mutual Fund' })).toBeInTheDocument();
  });

  it('defaults record type to Stock', () => {
    const { container } = renderModal();
    expect(screen.getByLabelText('record type')).toHaveValue('STOCK');
    expect(container.querySelector('input[name="asset_symbol"]')).toBeInTheDocument();
  });
});

describe('TransactionModal STOCK_SPLIT behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderModal = ({ initialData = null, selection = null } = {}) => {
    api.fetchPortfolios.mockResolvedValueOnce([
      { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
      { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
    ]);
    return render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
          { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
        ]}
        initialSelection={selection}
        disableFetch
      >
        <TransactionModal
          isOpen
          onClose={vi.fn()}
          onSuccess={vi.fn()}
          initialData={initialData}
        />
      </PortfolioProvider>
    );
  };

  it('shows portfolio dropdown with real portfolios only', () => {
    renderModal();
    const sel = screen.getByLabelText('portfolio');
    expect(sel).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Default Portfolio' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'All Portfolios' })).not.toBeInTheDocument();
  });

  it('selecting STOCK_SPLIT changes form layout', () => {
    const { container } = renderModal();
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'STOCK_SPLIT' } });
    expect(container.querySelector('input[name="split_from"]')).toBeInTheDocument();
    expect(container.querySelector('input[name="split_to"]')).toBeInTheDocument();
  });

  it('explains stock split versus new ticker stock allocations', () => {
    renderModal();
    expect(screen.getByText(/use STOCK_SPLIT only when the same ticker/i)).toBeInTheDocument();
    expect(screen.getByText(/record the received ticker as a BUY/i)).toBeInTheDocument();
    expect(screen.getByText(/Price \/ Share set to 0/i)).toBeInTheDocument();
  });

  it('hides price and fee fields for STOCK_SPLIT', () => {
    const { container } = renderModal();
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'STOCK_SPLIT' } });
    expect(container.querySelector('input[name="price_per_share"]')).not.toBeInTheDocument();
    expect(container.querySelector('input[name="fees"]')).not.toBeInTheDocument();
  });

  it('prevents invalid split ratio submission', async () => {
    const { container } = renderModal();
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'STOCK_SPLIT' } });
    fireEvent.change(container.querySelector('input[name="split_from"]'), { target: { value: '0' } });
    fireEvent.change(container.querySelector('input[name="split_to"]'), { target: { value: '20' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByText('split_from and split_to must be greater than 0')).toBeInTheDocument();
      expect(api.createTransaction).not.toHaveBeenCalled();
    });
  });

  it('submits stock BUY with unchanged payload shape', async () => {
    api.createTransaction.mockResolvedValueOnce({});
    const onSuccess = vi.fn();
    const { container } = render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
        ]}
        disableFetch
      >
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={onSuccess} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '10' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '150' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(api.createTransaction).toHaveBeenCalledWith(
        expect.objectContaining({
          asset_symbol: 'AAPL',
          type: 'BUY',
          quantity: 10,
          price_per_share: 150,
          portfolio_id: 1,
        })
      );
      expect(api.createTransaction.mock.calls[0][0].asset_type).toBeUndefined();
      expect(onSuccess).toHaveBeenCalledWith({ kind: 'asset' });
    });
  });

  it('submits zero-price stock BUY for received new-ticker allocations', async () => {
    api.createTransaction.mockResolvedValueOnce({});
    const { container } = render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
        ]}
        disableFetch
      >
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'NEWCO' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '4' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '0' } });
    fireEvent.change(container.querySelector('input[name="fees"]'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(api.createTransaction).toHaveBeenCalledWith(
        expect.objectContaining({
          asset_symbol: 'NEWCO',
          type: 'BUY',
          quantity: 4,
          price_per_share: 0,
          fees: 0,
          portfolio_id: 1,
        })
      );
    });
  });
});

describe('TransactionModal MUTUAL_FUND behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderModal = ({ initialData = null } = {}) =>
    render(
      <PortfolioProvider
        initialPortfolios={[
          { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
        ]}
        disableFetch
      >
        <TransactionModal
          isOpen
          onClose={vi.fn()}
          onSuccess={vi.fn()}
          initialData={initialData}
        />
      </PortfolioProvider>
    );

  const editTransaction = {
    id: 99, asset_type: 'MUTUAL_FUND', scheme_code: '120503', scheme_name: 'Test Fund',
    folio_number: 'F1', type: 'SELL', investment_date: '2026-03-10', nav_date: '2026-03-15',
    nav: '42.5', units_allotted: '100.125', paid_value: '4255.25', market_value: '4250.75',
    fees: '4.25', currency: 'INR', portfolio_id: 1, actual_cash_received: '4200',
    settlement_note: 'Statement settlement', fund_house: 'Test AMC', scheme_type: 'Open Ended',
    scheme_category: 'Equity', direct_or_regular: 'Direct', growth_or_idcw: 'Growth',
  };

  it('blocks loading and missing NAV without falling back to the original, then retries', async () => {
    let resolveLookup;
    api.getCachedMutualFundNav.mockImplementationOnce(() => new Promise((resolve) => { resolveLookup = resolve; }));
    const { container } = renderModal({ initialData: editTransaction });
    const save = screen.getByRole('button', { name: 'Save' });
    expect(screen.getByLabelText('NAV')).toHaveAttribute('readonly');
    expect(screen.getByLabelText('NAV')).toHaveValue(null);
    expect(save).toBeDisabled();
    fireEvent.submit(container.querySelector('form'));
    expect(api.updateTransaction).not.toHaveBeenCalled();
    await act(async () => resolveLookup({ scheme_code: '120503', nav_date: '2026-03-15', nav: null, status: 'missing' }));
    expect(screen.getByText('No cached NAV for this exact date.')).toBeInTheDocument();
    expect(save).toBeDisabled();
    fireEvent.submit(container.querySelector('form'));
    expect(api.updateTransaction).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Retry NAV lookup' }));
    await waitFor(() => expect(save).toBeEnabled());
    expect(api.getCachedMutualFundNav).toHaveBeenLastCalledWith('120503', '2026-03-15');
    expect(screen.getByLabelText('NAV')).toHaveValue(42.5);
  });

  it('blocks lookup errors and permits a retry', async () => {
    api.getCachedMutualFundNav.mockRejectedValueOnce(new Error('Offline'));
    const { container } = renderModal({ initialData: editTransaction });
    await screen.findByText('Cached NAV lookup failed.');
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    fireEvent.submit(container.querySelector('form'));
    expect(api.updateTransaction).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Retry NAV lookup' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled());
  });

  it('looks up NAV again when switching edit records with the same scheme and date', async () => {
    const view = (initialData) => (
      <PortfolioProvider initialPortfolios={[
        { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
      ]} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} initialData={initialData} />
      </PortfolioProvider>
    );
    const { rerender } = render(view(editTransaction));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled());
    rerender(view({ ...editTransaction, id: 100, folio_number: 'F2' }));
    await waitFor(() => expect(api.getCachedMutualFundNav).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled());
    expect(screen.getByDisplayValue('F2')).toBeInTheDocument();
  });

  it('ignores stale lookup responses after scheme and date changes', async () => {
    const pending = [];
    api.getCachedMutualFundNav.mockImplementation((scheme_code, nav_date) => new Promise((resolve, reject) => {
      pending.push({ scheme_code, nav_date, resolve, reject });
    }));
    const { container } = renderModal();
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'MUTUAL_FUND' } });
    const change = (name, value) => fireEvent.change(container.querySelector(`input[name="${name}"]`), { target: { value } });
    change('scheme_code', '120503');
    change('nav_date', '2026-03-15');
    change('scheme_code', '120504');
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    const latest = pending.at(-1);
    await act(async () => latest.resolve({ ...latest, status: 'available', nav: '50.1234' }));
    expect(screen.getByLabelText('NAV')).toHaveValue(50.1234);
    await act(async () => {
      pending[0].reject(new Error('Stale error'));
      pending.slice(1, -1).forEach((p) => p.resolve({ ...p, status: 'available', nav: '10' }));
    });
    expect(screen.getByLabelText('NAV')).toHaveValue(50.1234);
    expect(screen.queryByText('Cached NAV lookup failed.')).not.toBeInTheDocument();
    change('nav_date', '');
    expect(screen.getByLabelText('NAV')).toHaveValue(null);
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  });

  const missingLookup = () => api.getCachedMutualFundNav.mockImplementation(async (scheme_code, nav_date) => ({
    scheme_code, nav_date, nav: null, status: 'missing',
  }));
  const fetchResult = (overrides = {}) => ({
    scheme_code: '120503', nav_date: '2026-03-15', outcome: 'fetched', nav: '42.500000',
    status: 'available', retry_after_seconds: null, failure_category: null, attempt_id: null, ...overrides,
  });

  it('fetches a confirmed missing NAV once, showing progress, and unlocks save on success', async () => {
    missingLookup();
    let resolveFetch;
    api.fetchMissingMutualFundNav.mockImplementation(() => new Promise((resolve) => { resolveFetch = resolve; }));
    renderModal({ initialData: { ...editTransaction, nav: '42.5' } });
    const fetchButton = await screen.findByRole('button', { name: 'Fetch missing NAV' });
    expect(screen.getByRole('button', { name: 'Retry NAV lookup' })).toBeInTheDocument();
    fireEvent.click(fetchButton);
    fireEvent.click(fetchButton);
    expect(api.fetchMissingMutualFundNav).toHaveBeenCalledTimes(1);
    expect(api.fetchMissingMutualFundNav).toHaveBeenCalledWith('120503', '2026-03-15');
    expect(screen.getByText('Fetching NAV from MFAPI...')).toBeInTheDocument();
    expect(fetchButton).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    await act(async () => resolveFetch(fetchResult()));
    expect(screen.getByLabelText('NAV')).toHaveValue(42.5);
    expect(screen.getByText('Fetched NAV from MFAPI for this exact date.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
    expect(api.createTransaction).not.toHaveBeenCalled();
    expect(api.updateTransaction).not.toHaveBeenCalled();
  });

  it('does not offer a provider fetch when the cache lookup itself failed', async () => {
    api.getCachedMutualFundNav.mockRejectedValue(new Error('DB down'));
    renderModal({ initialData: editTransaction });
    await screen.findByText('Cached NAV lookup failed.');
    expect(screen.queryByRole('button', { name: 'Fetch missing NAV' })).not.toBeInTheDocument();
    expect(api.fetchMissingMutualFundNav).not.toHaveBeenCalled();
  });

  it('shows cooldown with a countdown, keeps save blocked and NAV read-only, then re-enables fetch', async () => {
    missingLookup();
    api.fetchMissingMutualFundNav.mockResolvedValueOnce(fetchResult({
      outcome: 'cooldown', nav: null, status: 'missing', retry_after_seconds: 1,
      failure_category: 'cooldown', attempt_id: 'a1b2',
    }));
    renderModal({ initialData: editTransaction });
    fireEvent.click(await screen.findByRole('button', { name: 'Fetch missing NAV' }));
    expect(await screen.findByText(/A recent fetch for this NAV failed\. Try again in 1s\./)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fetch missing NAV' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(screen.getByLabelText('NAV')).toHaveAttribute('readonly');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Fetch missing NAV' })).toBeEnabled(),
      { timeout: 2500 });
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  });

  it.each([
    ['date_unavailable', 'MFAPI has no NAV for this exact date.'],
    ['timeout', 'MFAPI timed out.'],
    ['provider_failure', 'MFAPI fetch failed.'],
    ['in_flight', 'A fetch for this NAV is already in progress.'],
  ])('reports %s without unlocking save', async (outcome, message) => {
    missingLookup();
    api.fetchMissingMutualFundNav.mockResolvedValueOnce(fetchResult({
      outcome, nav: null, status: 'missing', retry_after_seconds: 60, failure_category: outcome,
    }));
    renderModal({ initialData: editTransaction });
    fireEvent.click(await screen.findByRole('button', { name: 'Fetch missing NAV' }));
    expect(await screen.findByText(new RegExp(`${message.replace(/\./g, '\\.')} Try again in 60s\\.`))).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(screen.getByLabelText('NAV')).toHaveValue(null);
  });

  it('reports a failed fetch request without treating it as a NAV', async () => {
    missingLookup();
    api.fetchMissingMutualFundNav.mockRejectedValueOnce(new Error('Offline'));
    renderModal({ initialData: editTransaction });
    fireEvent.click(await screen.findByRole('button', { name: 'Fetch missing NAV' }));
    expect(await screen.findByText('NAV fetch request failed.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fetch missing NAV' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  });

  it('ignores a fetch response that arrives after the scheme or date changed', async () => {
    missingLookup();
    let resolveFetch;
    api.fetchMissingMutualFundNav.mockImplementation(() => new Promise((resolve) => { resolveFetch = resolve; }));
    const { container } = renderModal({ initialData: editTransaction });
    fireEvent.click(await screen.findByRole('button', { name: 'Fetch missing NAV' }));
    fireEvent.change(container.querySelector('input[name="nav_date"]'), { target: { value: '2026-03-16' } });
    await screen.findByText('No cached NAV for this exact date.');
    await act(async () => resolveFetch(fetchResult()));
    expect(screen.getByLabelText('NAV')).toHaveValue(null);
    expect(screen.queryByText('Fetched NAV from MFAPI for this exact date.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    fireEvent.change(container.querySelector('input[name="nav_date"]'), { target: { value: '2026-03-15' } });
    await screen.findByText('No cached NAV for this exact date.');
    expect(screen.getByLabelText('NAV')).toHaveValue(null);
  });

  const fillProvisionalBuy = async ({ fees = '4.64' } = {}) => {
    missingLookup();
    api.fetchMissingMutualFundNav.mockResolvedValueOnce(fetchResult({
      outcome: 'date_unavailable', nav: null, status: 'missing', retry_after_seconds: 60,
      failure_category: 'date_unavailable', attempt_id: 'att-1',
    }));
    const utils = renderModal();
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'MUTUAL_FUND' } });
    const set = (name, value) => fireEvent.change(
      utils.container.querySelector(`input[name="${name}"]`), { target: { value } });
    set('scheme_code', '120503');
    set('scheme_name', 'Test Fund');
    set('folio_number', 'F1');
    set('investment_date', '2026-03-15');
    set('nav_date', '2026-03-15');
    set('units_allotted', '65.4321');
    set('paid_value', '1005');
    set('fees', fees);
    fireEvent.click(await screen.findByRole('button', { name: 'Fetch missing NAV' }));
    await screen.findByRole('group', { name: 'Provisional NAV entry' });
    set('provisional_nav', '15.2885');
    return { ...utils, set };
  };
  const previewOk = (overrides = {}) => ({
    scheme_code: '120503', nav_date: '2026-03-15', nav: '15.288500', units_allotted: '65.43210000',
    market_value: '1000.3587', nav_source: 'PROVISIONAL_USER', status: 'provisional', ...overrides,
  });

  it('saves a provisional BUY only after server market value and both confirmations', async () => {
    api.previewProvisionalMutualFundNav.mockResolvedValueOnce(previewOk());
    api.createTransaction.mockResolvedValueOnce({ id: 7 });
    const { container } = await fillProvisionalBuy();
    const save = screen.getByRole('button', { name: 'Save' });
    expect(save).toBeDisabled();
    expect(screen.getByLabelText('NAV')).toHaveAttribute('readonly');
    expect(screen.getByLabelText('NAV')).toHaveValue(null);
    expect(screen.getByText('Provisional NAV (unverified)')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Get market value' }));
    expect(await screen.findByText('Market value from server: 1000.3587 INR (unverified).')).toBeInTheDocument();
    expect(api.previewProvisionalMutualFundNav).toHaveBeenCalledWith({
      schemeCode: '120503', navDate: '2026-03-15', provisionalNav: '15.2885',
      unitsAllotted: '65.4321', attemptId: 'att-1', transactionId: null, type: 'BUY',
    });
    const marketValue = container.querySelector('input[name="market_value"]');
    expect(marketValue).toHaveValue(1000.3587);
    expect(marketValue).toHaveAttribute('readonly');
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: /provisional and unverified/ }));
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: /actual amount I paid/ }));
    expect(save).toBeEnabled();

    fireEvent.click(save);
    await waitFor(() => expect(api.createTransaction).toHaveBeenCalledTimes(1));
    expect(api.createTransaction).toHaveBeenCalledWith(expect.objectContaining({
      type: 'BUY', nav_date: '2026-03-15', units_allotted: 65.4321, paid_value: 1005, fees: 4.64,
      nav: 15.2885, market_value: 1000.3587, provisional_nav: '15.2885',
      provisional_attempt_id: 'att-1', confirm_provisional_nav: true, confirm_paid_value: true,
    }));
  });

  it('invalidates the server market value when units change', async () => {
    api.previewProvisionalMutualFundNav.mockResolvedValueOnce(previewOk());
    const { container, set } = await fillProvisionalBuy();
    fireEvent.click(screen.getByRole('button', { name: 'Get market value' }));
    await screen.findByText(/Market value from server/);
    fireEvent.click(screen.getByRole('checkbox', { name: /provisional and unverified/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /actual amount I paid/ }));
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
    set('units_allotted', '70');
    expect(container.querySelector('input[name="market_value"]')).toHaveValue(null);
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(screen.queryByText(/Market value from server/)).not.toBeInTheDocument();
  });

  it('requires fees with a provisional NAV instead of inferring them', async () => {
    api.previewProvisionalMutualFundNav.mockResolvedValueOnce(previewOk());
    const { container } = await fillProvisionalBuy({ fees: '' });
    fireEvent.click(screen.getByRole('button', { name: 'Get market value' }));
    await screen.findByText(/Market value from server/);
    fireEvent.click(screen.getByRole('checkbox', { name: /provisional and unverified/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /actual amount I paid/ }));
    fireEvent.submit(container.querySelector('form'));
    expect(await screen.findByText('Fees are required with a provisional NAV (enter 0 if none).')).toBeInTheDocument();
    expect(api.createTransaction).not.toHaveBeenCalled();
  });

  it('surfaces a rejected preview and keeps save blocked', async () => {
    api.previewProvisionalMutualFundNav.mockRejectedValueOnce(new Error('No matching unsuccessful NAV fetch'));
    await fillProvisionalBuy();
    fireEvent.click(screen.getByRole('button', { name: 'Get market value' }));
    expect(await screen.findByText('No matching unsuccessful NAV fetch')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: /provisional and unverified/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /actual amount I paid/ }));
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  });

  it('does not offer provisional entry without unsuccessful attempt evidence', async () => {
    missingLookup();
    api.fetchMissingMutualFundNav.mockResolvedValueOnce(fetchResult({
      outcome: 'in_flight', nav: null, status: 'missing', retry_after_seconds: 5, attempt_id: null,
    }));
    renderModal({ initialData: { ...editTransaction, type: 'BUY' } });
    fireEvent.click(await screen.findByRole('button', { name: 'Fetch missing NAV' }));
    await screen.findByText(/already in progress/);
    expect(screen.queryByRole('group', { name: 'Provisional NAV entry' })).not.toBeInTheDocument();
  });

  it('keeps an existing provisional BUY editable without a new fetch', async () => {
    missingLookup();
    api.previewProvisionalMutualFundNav.mockResolvedValueOnce(previewOk({ market_value: '4255.3125' }));
    renderModal({ initialData: {
      ...editTransaction, type: 'BUY', nav_source: 'PROVISIONAL_USER', nav_provisional: true,
      nav_verification_status: 'NAV_MISSING',
    } });
    await screen.findByRole('group', { name: 'Provisional NAV entry' });
    expect(screen.getAllByText('Provisional NAV (unverified)').length).toBeGreaterThan(0);
    expect(screen.getByLabelText('Provisional NAV')).toHaveValue(42.5);
    fireEvent.click(screen.getByRole('button', { name: 'Get market value' }));
    await screen.findByText(/Market value from server: 4255.3125/);
    expect(api.previewProvisionalMutualFundNav).toHaveBeenCalledWith(expect.objectContaining({
      attemptId: null, transactionId: 99, provisionalNav: '42.5',
    }));
    expect(api.fetchMissingMutualFundNav).not.toHaveBeenCalled();
  });

  const fillProvisionalSell = async () => {
    const utils = await fillProvisionalBuy({ fees: '2' });
    fireEvent.change(utils.container.querySelector('select[name="type"]'), { target: { value: 'SELL' } });
    utils.set('units_allotted', '40');
    utils.set('paid_value', '1700');
    utils.set('actual_cash_received', '1650');
    utils.set('provisional_nav', '42.5');
    return utils;
  };
  const sellPreviewOk = (overrides = {}) => previewOk({
    nav: '42.500000', units_allotted: '40.00000000', market_value: '1700.0000', type: 'SELL',
    calculated_proceeds: '1700.0000', tax_withheld: '50.0000', tax_released: '0.0000', ...overrides,
  });

  it('saves a provisional SELL with server market value, proceeds and tax gap', async () => {
    api.previewProvisionalMutualFundNav.mockResolvedValueOnce(sellPreviewOk());
    api.createTransaction.mockResolvedValueOnce({ id: 8 });
    const { container } = await fillProvisionalSell();
    expect(screen.getByRole('group', { name: 'Provisional NAV entry' })).toBeInTheDocument();
    expect(screen.queryByText(/Calculated proceeds/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Get market value' }));
    expect(await screen.findByText('Market value from server: 1700.0000 INR (unverified).')).toBeInTheDocument();
    expect(api.previewProvisionalMutualFundNav).toHaveBeenCalledWith({
      schemeCode: '120503', navDate: '2026-03-15', provisionalNav: '42.5', unitsAllotted: '40',
      attemptId: 'att-1', transactionId: null, type: 'SELL', paidValue: '1700', fees: '2',
      actualCashReceived: '1650',
    });
    expect(screen.getByText(/Calculated proceeds from server: 1700.00 INR/)).toBeInTheDocument();
    expect(screen.getByText(/Tax withheld \/ broker adjustment: 50.00 INR/)).toBeInTheDocument();
    expect(container.querySelector('input[name="market_value"]')).toHaveValue(1700);
    const save = screen.getByRole('button', { name: 'Save' });
    fireEvent.click(screen.getByRole('checkbox', { name: /provisional and unverified/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /actual redemption proceeds/ }));
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(api.createTransaction).toHaveBeenCalledTimes(1));
    expect(api.createTransaction).toHaveBeenCalledWith(expect.objectContaining({
      type: 'SELL', units_allotted: 40, paid_value: 1700, fees: 2, actual_cash_received: 1650,
      market_value: 1700, provisional_nav: '42.5', provisional_attempt_id: 'att-1',
      confirm_provisional_nav: true, confirm_paid_value: true,
    }));
  });

  it('invalidates the SELL server preview when settlement inputs change', async () => {
    api.previewProvisionalMutualFundNav.mockResolvedValueOnce(sellPreviewOk());
    const { set } = await fillProvisionalSell();
    fireEvent.click(screen.getByRole('button', { name: 'Get market value' }));
    await screen.findByText(/Calculated proceeds from server/);
    fireEvent.click(screen.getByRole('checkbox', { name: /provisional and unverified/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /actual redemption proceeds/ }));
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
    set('actual_cash_received', '1600');
    expect(screen.queryByText(/Calculated proceeds/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Tax withheld/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  });

  it('keeps an existing provisional SELL editable without a fetch, but not after a type change', async () => {
    missingLookup();
    api.previewProvisionalMutualFundNav.mockResolvedValueOnce(sellPreviewOk({
      market_value: '4255.3125', calculated_proceeds: '4255.2500', tax_withheld: '55.2500',
    }));
    const { container } = renderModal({ initialData: {
      ...editTransaction, nav_source: 'PROVISIONAL_USER', nav_provisional: true,
      nav_verification_status: 'NAV_MISSING',
    } });
    await screen.findByRole('group', { name: 'Provisional NAV entry' });
    expect(screen.getAllByText('Provisional NAV (unverified)').length).toBeGreaterThan(1);
    expect(screen.getByLabelText('Provisional NAV')).toHaveValue(42.5);
    fireEvent.click(screen.getByRole('button', { name: 'Get market value' }));
    await screen.findByText(/Calculated proceeds from server: 4255.25 INR/);
    expect(api.previewProvisionalMutualFundNav).toHaveBeenCalledWith(expect.objectContaining({
      attemptId: null, transactionId: 99, type: 'SELL', paidValue: '4255.25', fees: '4.25',
      actualCashReceived: '4200',
    }));
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'BUY' } });
    expect(screen.queryByRole('group', { name: 'Provisional NAV entry' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fetch missing NAV' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(api.fetchMissingMutualFundNav).not.toHaveBeenCalled();
  });

  it('keeps a rejected provisional SELL edit on screen for review', async () => {
    missingLookup();
    api.previewProvisionalMutualFundNav.mockResolvedValueOnce(sellPreviewOk({
      market_value: '4255.3125', calculated_proceeds: '4000.0000', tax_withheld: '0.0000',
      tax_released: '200.0000',
    }));
    api.updateTransaction.mockRejectedValueOnce(
      new Error('This transaction change would make future cash balance negative.'));
    const onClose = vi.fn();
    const { container } = render(
      <PortfolioProvider initialPortfolios={[
        { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
      ]} disableFetch>
        <TransactionModal isOpen onClose={onClose} onSuccess={vi.fn()} initialData={{
          ...editTransaction, nav_source: 'PROVISIONAL_USER', nav_provisional: true,
        }} />
      </PortfolioProvider>
    );
    await screen.findByRole('group', { name: 'Provisional NAV entry' });
    fireEvent.change(container.querySelector('input[name="paid_value"]'), { target: { value: '4000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Get market value' }));
    await screen.findByText(/Calculated proceeds from server: 4000.00 INR/);
    fireEvent.click(screen.getByRole('checkbox', { name: /provisional and unverified/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /actual redemption proceeds/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('This transaction change would make future cash balance negative.'))
      .toBeInTheDocument();
    expect(api.updateTransaction).toHaveBeenCalledWith(99, expect.objectContaining({
      type: 'SELL', paid_value: 4000, provisional_nav: '42.5', confirm_provisional_nav: true,
    }));
    expect(api.updateTransaction.mock.calls[0][1]).not.toHaveProperty('provisional_attempt_id');
    expect(onClose).not.toHaveBeenCalled();
    expect(container.querySelector('input[name="paid_value"]')).toHaveValue(4000);
    expect(screen.getByLabelText('Provisional NAV')).toHaveValue(42.5);
    expect(screen.getByText(/Withheld tax released: 200.00 INR/)).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /provisional and unverified/ })).toBeChecked();
  });

  it('tells the user a cached NAV now replaces the provisional NAV on edit', async () => {
    renderModal({ initialData: {
      ...editTransaction, nav: '42.5', nav_source: 'PROVISIONAL_USER', nav_provisional: true,
      nav_verification_status: 'NAV_MISMATCH', provisional_superseded_by_cache: true,
    } });
    expect(await screen.findByText(/saving replaces the provisional NAV with the cached NAV/)).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: 'Provisional NAV entry' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('NAV')).toHaveValue(42.5);
  });

  it('requires explicit replacement confirmation and preserves statement fields in an edit PUT', async () => {
    api.getCachedMutualFundNav.mockImplementation(async (scheme_code, nav_date) => ({
      scheme_code, nav_date, nav: '43.1250', status: 'available',
    }));
    const actual = await vi.importActual('../api');
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ id: 99 }) });
    vi.stubGlobal('fetch', fetchMock);
    api.updateTransaction.mockImplementationOnce(actual.updateTransaction);
    try {
      const { container } = renderModal({ initialData: editTransaction });
      const confirmation = await screen.findByRole('checkbox', { name: /Apply cached NAV 43.1250 instead of original NAV 42.5/ });
      expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
      fireEvent.submit(container.querySelector('form'));
      expect(api.updateTransaction).not.toHaveBeenCalled();
      fireEvent.click(confirmation);
      expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
      fireEvent.change(container.querySelector('input[name="nav_date"]'), { target: { value: '2026-03-16' } });
      await waitFor(() => expect(screen.getByLabelText('NAV')).toHaveValue(43.125));
      expect(screen.getByRole('checkbox')).not.toBeChecked();
      fireEvent.click(screen.getByRole('checkbox'));
      fireEvent.click(screen.getByRole('button', { name: 'Save' }));
      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
      expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/transactions/99');
      const request = fetchMock.mock.calls[0][1];
      expect(request.method).toBe('PUT');
      expect(JSON.parse(request.body)).toEqual({
        asset_type: 'MUTUAL_FUND', scheme_code: '120503', scheme_name: 'Test Fund', folio_number: 'F1',
        type: 'SELL', investment_date: '2026-03-10', nav_date: '2026-03-16', nav: 43.125,
        units_allotted: 100.125, paid_value: 4255.25, market_value: 4250.75, fees: 4.25,
        currency: 'INR', portfolio_id: 1, actual_cash_received: 4200, settlement_note: 'Statement settlement',
        fund_house: 'Test AMC', scheme_type: 'Open Ended', scheme_category: 'Equity',
        direct_or_regular: 'Direct', growth_or_idcw: 'Growth',
      });
      expect(api.createTransaction).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('uses the authenticated exact-date lookup API with encoded parameters', async () => {
    const actual = await vi.importActual('../api');
    const result = { scheme_code: '120503', nav_date: '2026-03-15', nav: '42.5000', status: 'available' };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => result });
    vi.stubGlobal('fetch', fetchMock);
    try {
      expect(await actual.getCachedMutualFundNav('120503', '2026-03-15')).toEqual(result);
      expect(fetchMock).toHaveBeenCalledWith('/api/v1/nav/lookup?scheme_code=120503&nav_date=2026-03-15',
        expect.objectContaining({ credentials: 'include' }));
      expect(fetchMock.mock.calls[0][1].method ?? 'GET').toBe('GET');
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('switches to mutual fund form mode', () => {
    const { container } = renderModal();
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'MUTUAL_FUND' } });
    expect(container.querySelector('input[name="scheme_code"]')).toBeInTheDocument();
    expect(container.querySelector('input[name="asset_symbol"]')).not.toBeInTheDocument();
  });

  it('submits MF create with backend field names', async () => {
    api.createTransaction.mockResolvedValueOnce({});
    const { container } = renderModal();
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'MUTUAL_FUND' } });
    fireEvent.change(container.querySelector('input[name="scheme_code"]'), { target: { value: '120503' } });
    fireEvent.change(container.querySelector('input[name="scheme_name"]'), { target: { value: 'Test Fund' } });
    fireEvent.change(container.querySelector('input[name="folio_number"]'), { target: { value: 'F1' } });
    fireEvent.change(container.querySelector('input[name="investment_date"]'), { target: { value: '2026-03-10' } });
    fireEvent.change(container.querySelector('input[name="nav_date"]'), { target: { value: '2026-03-15' } });
    await waitFor(() => expect(container.querySelector('input[name="nav"]')).toHaveValue(42.5));
    fireEvent.change(container.querySelector('input[name="units_allotted"]'), { target: { value: '100' } });
    fireEvent.change(container.querySelector('input[name="paid_value"]'), { target: { value: '4255' } });
    fireEvent.change(container.querySelector('input[name="market_value"]'), { target: { value: '4250' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(api.createTransaction).toHaveBeenCalledWith(
        expect.objectContaining({
          asset_type: 'MUTUAL_FUND',
          scheme_code: '120503',
          portfolio_id: 1,
        })
      );
    });
  });

  it('pre-fills MF edit fields and sends PUT payload', async () => {
    api.updateTransaction.mockResolvedValueOnce({});
    const mfTxn = {
      id: 99,
      asset_type: 'MUTUAL_FUND',
      scheme_code: '120503',
      scheme_name: 'Test Fund',
      folio_number: 'F1',
      type: 'BUY',
      investment_date: '2026-03-10',
      nav_date: '2026-03-15',
      nav: 42.5,
      units_allotted: 100,
      paid_value: 4255,
      market_value: 4250,
      currency: 'INR',
      portfolio_id: 1,
      nav_verification_status: 'NAV_MISSING',
      nav_verification_message: 'No cached NAV for this date',
    };
    const { container } = renderModal({ initialData: mfTxn });
    expect(screen.getByLabelText('record type')).toBeDisabled();
    expect(screen.getByDisplayValue('120503')).toBeDisabled();

    fireEvent.change(container.querySelector('input[name="paid_value"]'), { target: { value: '4300' } });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(api.updateTransaction).toHaveBeenCalledWith(
        99,
        expect.objectContaining({ paid_value: 4300 })
      );
    });
  });
});

describe('TransactionModal CASH behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const portfolios = [
    { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
    { id: 2, name: 'P2', is_default: false, is_active: true, base_currency: 'EUR' },
  ];

  it('submits cash deposit via createCashDeposit', async () => {
    api.createCashDeposit.mockResolvedValueOnce({});
    const onSuccess = vi.fn();
    render(
      <PortfolioProvider initialPortfolios={portfolios} initialSelection={{ mode: 'portfolio', id: 1, name: 'Default Portfolio' }} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={onSuccess} />
      </PortfolioProvider>
    );
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'CASH' } });
    fireEvent.change(screen.getByLabelText('cash action'), { target: { value: 'deposit' } });
    fireEvent.change(screen.getByLabelText('cash currency'), { target: { value: 'EUR' } });
    fireEvent.change(document.getElementById('txn-modal-cash-amount'), { target: { value: '1000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record deposit' }));

    await waitFor(() => {
      expect(api.createCashDeposit).toHaveBeenCalledWith(
        expect.objectContaining({
          portfolio_id: 1,
          currency: 'EUR',
          amount: 1000,
        })
      );
      expect(api.createTransaction).not.toHaveBeenCalled();
      expect(onSuccess).toHaveBeenCalledWith({ kind: 'cash', message: 'Deposit recorded.' });
    });
  });

  it('submits cash withdrawal via createCashWithdrawal', async () => {
    api.createCashWithdrawal.mockResolvedValueOnce({});
    render(
      <PortfolioProvider initialPortfolios={portfolios} initialSelection={{ mode: 'portfolio', id: 1, name: 'Default Portfolio' }} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'CASH' } });
    fireEvent.change(screen.getByLabelText('cash action'), { target: { value: 'withdrawal' } });
    fireEvent.change(document.getElementById('txn-modal-cash-amount'), { target: { value: '50' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record withdrawal' }));

    await waitFor(() => {
      expect(api.createCashWithdrawal).toHaveBeenCalledWith(
        expect.objectContaining({ portfolio_id: 1, amount: 50 })
      );
    });
  });

  it('shows insufficient cash shortfall from CashApiError', async () => {
    api.createCashWithdrawal.mockRejectedValueOnce(
      new CashApiError('Insufficient cash balance for withdrawal.', {
        required: 500,
        available: 100,
        shortfall: 400,
        currency: 'EUR',
      })
    );
    render(
      <PortfolioProvider initialPortfolios={portfolios} initialSelection={{ mode: 'portfolio', id: 1, name: 'Default Portfolio' }} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'CASH' } });
    fireEvent.change(screen.getByLabelText('cash action'), { target: { value: 'withdrawal' } });
    fireEvent.change(document.getElementById('txn-modal-cash-amount'), { target: { value: '500' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record withdrawal' }));

    await waitFor(() => {
      expect(screen.getByText('Insufficient cash balance for withdrawal.')).toBeInTheDocument();
      expect(screen.getByText(/Shortfall:/)).toBeInTheDocument();
    });
  });

  it('requires portfolio selection in All Portfolios scope', async () => {
    render(
      <PortfolioProvider initialPortfolios={portfolios} initialSelection={{ mode: 'all' }} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'CASH' } });
    fireEvent.change(document.getElementById('txn-modal-cash-amount'), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record deposit' }));

    await waitFor(() => {
      expect(screen.getByText('Select a portfolio.')).toBeInTheDocument();
      expect(api.createCashDeposit).not.toHaveBeenCalled();
    });
  });

  it('preselects portfolio when sidebar scope is a single portfolio', async () => {
    api.createCashDeposit.mockResolvedValueOnce({});
    render(
      <PortfolioProvider
        initialPortfolios={portfolios}
        initialSelection={{ mode: 'portfolio', id: 2, name: 'P2' }}
        disableFetch
      >
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'CASH' } });
    fireEvent.change(document.getElementById('txn-modal-cash-amount'), { target: { value: '25' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record deposit' }));

    await waitFor(() => {
      expect(api.createCashDeposit).toHaveBeenCalledWith(
        expect.objectContaining({ portfolio_id: 2 })
      );
    });
  });

  it('shows hint that cash entries are edited on Cash page', () => {
    render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'CASH' } });
    expect(
      screen.getByText('Cash entries can be edited from the Cash page.')
    ).toBeInTheDocument();
  });
});

describe('TransactionModal stock/MF BUY insufficient cash', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const portfolios = [
    { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
  ];

  const renderWithRouter = (ui) =>
    render(<MemoryRouter>{ui}</MemoryRouter>);

  const purchaseShortfallError = new TransactionApiError(
    'Insufficient cash balance for purchase.',
    {
      required: 1005,
      available: 500,
      shortfall: 505,
      currency: 'EUR',
    }
  );

  it('stock BUY shows required, available, shortfall, and currency', async () => {
    api.createTransaction.mockRejectedValueOnce(purchaseShortfallError);
    const onClose = vi.fn();
    const { container } = renderWithRouter(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={onClose} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '10' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByText('Insufficient cash balance for purchase.')).toBeInTheDocument();
      expect(screen.getByText(/Required:/)).toBeInTheDocument();
      expect(screen.getByText(/Available:/)).toBeInTheDocument();
      expect(screen.getByText(/Shortfall:/)).toBeInTheDocument();
      expect(
        screen.getByText(
          'Purchases require cash in the transaction currency. Add or edit EUR cash in this portfolio, then retry.'
        )
      ).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Recommended action' })).toBeInTheDocument();
      expect(
        screen.getByText(/Add the missing EUR cash deposit and continue with this purchase/)
      ).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /open cash page/i })).toHaveAttribute('href', '/cash');
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('mutual fund BUY shows shortfall fields from TransactionApiError', async () => {
    api.createTransaction.mockRejectedValueOnce(purchaseShortfallError);
    const { container } = renderWithRouter(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'MUTUAL_FUND' } });
    fireEvent.change(container.querySelector('input[name="scheme_code"]'), { target: { value: '120503' } });
    fireEvent.change(container.querySelector('input[name="scheme_name"]'), { target: { value: 'Test Fund' } });
    fireEvent.change(container.querySelector('input[name="folio_number"]'), { target: { value: 'F1' } });
    fireEvent.change(container.querySelector('input[name="investment_date"]'), { target: { value: '2026-03-10' } });
    fireEvent.change(container.querySelector('input[name="nav_date"]'), { target: { value: '2026-03-15' } });
    await waitFor(() => expect(container.querySelector('input[name="nav"]')).toHaveValue(42.5));
    fireEvent.change(container.querySelector('input[name="units_allotted"]'), { target: { value: '100' } });
    fireEvent.change(container.querySelector('input[name="paid_value"]'), { target: { value: '4255' } });
    fireEvent.change(container.querySelector('input[name="market_value"]'), { target: { value: '4250' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByText('Insufficient cash balance for purchase.')).toBeInTheDocument();
      expect(screen.getByText(/Shortfall:/)).toBeInTheDocument();
      expect(
        screen.getByText(
          'Purchases require cash in the transaction currency. Add or edit EUR cash in this portfolio, then retry.'
        )
      ).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /open cash page/i })).toHaveAttribute('href', '/cash');
    });
  });

  it('cash withdrawal shortfall does not show add-and-continue panel', async () => {
    api.createCashWithdrawal.mockRejectedValueOnce(
      new CashApiError('Insufficient cash balance for withdrawal.', {
        required: 500,
        available: 100,
        shortfall: 400,
        currency: 'EUR',
      })
    );
    render(
      <PortfolioProvider initialPortfolios={portfolios} initialSelection={{ mode: 'portfolio', id: 1, name: 'Default Portfolio' }} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'CASH' } });
    fireEvent.change(screen.getByLabelText('cash action'), { target: { value: 'withdrawal' } });
    fireEvent.change(document.getElementById('txn-modal-cash-amount'), { target: { value: '500' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record withdrawal' }));

    await waitFor(() => {
      expect(screen.getByText(/Shortfall:/)).toBeInTheDocument();
      expect(
        screen.queryByText(/Purchases require cash in the transaction currency/)
      ).not.toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'Recommended action' })).not.toBeInTheDocument();
    });
  });

  it('add-and-continue creates EUR deposit from backend shortfall then retries BUY', async () => {
    api.createTransaction
      .mockRejectedValueOnce(purchaseShortfallError)
      .mockResolvedValueOnce({ id: 99 });
    api.createCashDeposit.mockResolvedValueOnce({ id: 1 });
    const onClose = vi.fn();
    const onSuccess = vi.fn();
    const { container } = renderWithRouter(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={onClose} onSuccess={onSuccess} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('input[name="date"]'), { target: { value: '2026-06-01' } });
    fireEvent.change(container.querySelector('input[name="currency"]'), { target: { value: 'USD' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '10' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Add missing cash and continue' })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText('Source of funds'), { target: { value: 'Broker transfer' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add missing cash and continue' }));

    await waitFor(() => {
      expect(api.createCashDeposit).toHaveBeenCalledWith({
        portfolio_id: 1,
        date: '2026-06-01',
        currency: 'EUR',
        amount: 505,
        source_of_funds: 'Broker transfer',
        note: 'Added before purchase of AAPL',
      });
      expect(api.createTransaction).toHaveBeenCalledTimes(2);
      expect(api.createTransaction).toHaveBeenLastCalledWith(
        expect.objectContaining({
          asset_symbol: 'AAPL',
          type: 'BUY',
          currency: 'USD',
          portfolio_id: 1,
        })
      );
      expect(onClose).toHaveBeenCalled();
      expect(onSuccess).toHaveBeenCalledWith({
        kind: 'asset',
        message: 'Cash deposit added and purchase recorded.',
      });
    });
  });

  it('shows partial success when deposit succeeds but retry BUY fails', async () => {
    api.createTransaction
      .mockRejectedValueOnce(purchaseShortfallError)
      .mockRejectedValueOnce(new TransactionApiError('Validation failed on retry.', {}));
    api.createCashDeposit.mockResolvedValueOnce({ id: 1 });
    const onClose = vi.fn();
    const { container } = renderWithRouter(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={onClose} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '10' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Add missing cash and continue' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add missing cash and continue' }));

    await waitFor(() => {
      expect(api.createCashDeposit).toHaveBeenCalledTimes(1);
      expect(
        screen.getByText(/Cash deposit was created, but the purchase could not be recorded/)
      ).toBeInTheDocument();
      expect(screen.getByText('Validation failed on retry.')).toBeInTheDocument();
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('MF BUY add-and-continue uses investment_date for deposit', async () => {
    api.createTransaction
      .mockRejectedValueOnce(
        new TransactionApiError('Insufficient cash balance for purchase.', {
          required: 4255,
          available: 0,
          shortfall: 4255,
          currency: 'INR',
        })
      )
      .mockResolvedValueOnce({ id: 2 });
    api.createCashDeposit.mockResolvedValueOnce({});
    const { container } = renderWithRouter(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(screen.getByLabelText('record type'), { target: { value: 'MUTUAL_FUND' } });
    fireEvent.change(container.querySelector('input[name="scheme_code"]'), { target: { value: '120503' } });
    fireEvent.change(container.querySelector('input[name="scheme_name"]'), { target: { value: 'Test Fund' } });
    fireEvent.change(container.querySelector('input[name="folio_number"]'), { target: { value: 'F1' } });
    fireEvent.change(container.querySelector('input[name="investment_date"]'), { target: { value: '2026-03-10' } });
    fireEvent.change(container.querySelector('input[name="nav_date"]'), { target: { value: '2026-03-15' } });
    await waitFor(() => expect(container.querySelector('input[name="nav"]')).toHaveValue(42.5));
    fireEvent.change(container.querySelector('input[name="units_allotted"]'), { target: { value: '100' } });
    fireEvent.change(container.querySelector('input[name="paid_value"]'), { target: { value: '4255' } });
    fireEvent.change(container.querySelector('input[name="market_value"]'), { target: { value: '4250' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Add missing cash and continue' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add missing cash and continue' }));
    await waitFor(() => {
      expect(api.createCashDeposit).toHaveBeenCalledWith(
        expect.objectContaining({
          date: '2026-03-10',
          currency: 'INR',
          amount: 4255,
          portfolio_id: 1,
        })
      );
    });
  });

  it('disables Save and add-and-continue while flow is running', async () => {
    let resolveDeposit;
    api.createTransaction.mockRejectedValueOnce(purchaseShortfallError);
    api.createCashDeposit.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveDeposit = resolve;
        })
    );
    const { container } = renderWithRouter(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '10' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Add missing cash and continue' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add missing cash and continue' }));
    await waitFor(() => {
      expect(screen.getByText('Adding cash and recording purchase…')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Add missing cash and continue' })).toBeDisabled();
    });
    resolveDeposit({});
    api.createTransaction.mockResolvedValueOnce({});
    await waitFor(() => {
      expect(api.createCashDeposit).toHaveBeenCalledTimes(1);
    });
  });

  it('double-click add-and-continue creates only one deposit', async () => {
    let resolveDeposit;
    const depositPromise = new Promise((resolve) => {
      resolveDeposit = resolve;
    });
    api.createTransaction.mockRejectedValueOnce(purchaseShortfallError).mockResolvedValueOnce({});
    api.createCashDeposit.mockReturnValue(depositPromise);
    const { container } = renderWithRouter(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '10' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Add missing cash and continue' })).toBeInTheDocument();
    });
    const btn = screen.getByRole('button', { name: 'Add missing cash and continue' });
    fireEvent.click(btn);
    fireEvent.click(btn);
    resolveDeposit({});
    await waitFor(() => {
      expect(api.createCashDeposit).toHaveBeenCalledTimes(1);
    });
  });

  it('edit transaction blocked by future-impact renders panel in modal', async () => {
    api.updateTransaction.mockRejectedValueOnce(
      new TransactionApiError(
        'This transaction change would make future cash balance negative.',
        {
          status: 409,
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
        }
      )
    );
    const initialData = {
      id: 5,
      asset_symbol: 'AAPL',
      date: '2026-06-05',
      type: 'SELL',
      quantity: 10,
      price_per_share: 100,
      currency: 'EUR',
      fees: 0,
      portfolio_id: 1,
    };
    render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal
          isOpen
          onClose={vi.fn()}
          onSuccess={vi.fn()}
          initialData={initialData}
        />
      </PortfolioProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(
        screen.getByText(/linked cash settlement funded later transactions/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/Affected ledger entries/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Shortfall:/)).not.toBeInTheDocument();
  });

  it('insufficient BUY edit still renders shortfall panel', async () => {
    api.updateTransaction.mockRejectedValueOnce(purchaseShortfallError);
    const initialData = {
      id: 5,
      asset_symbol: 'AAPL',
      date: '2026-06-01',
      type: 'BUY',
      quantity: 5,
      price_per_share: 100,
      currency: 'EUR',
      fees: 5,
      portfolio_id: 1,
    };
    const { container } = renderWithRouter(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal
          isOpen
          onClose={vi.fn()}
          onSuccess={vi.fn()}
          initialData={initialData}
        />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '25' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(screen.getByText(/Shortfall:/)).toBeInTheDocument();
    });
    expect(
      screen.queryByText(/linked cash settlement funded later transactions/i)
    ).not.toBeInTheDocument();
  });

  it('stock BUY generic validation error shows message without shortfall panel', async () => {
    api.createTransaction.mockRejectedValueOnce(
      new TransactionApiError('asset_symbol: This field is required.', {
        data: { asset_symbol: ['This field is required.'] },
      })
    );
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '1' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByText('asset_symbol: This field is required.')).toBeInTheDocument();
    });
    expect(screen.queryByText(/Shortfall:/)).not.toBeInTheDocument();
  });

  it('successful stock BUY closes modal and calls onSuccess', async () => {
    api.createTransaction.mockResolvedValueOnce({});
    const onClose = vi.fn();
    const onSuccess = vi.fn();
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={onClose} onSuccess={onSuccess} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '1' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
      expect(onSuccess).toHaveBeenCalledWith({ kind: 'asset' });
    });
    expect(screen.queryByText(/Shortfall:/)).not.toBeInTheDocument();
  });

  it('stock SELL does not show add-and-continue after failed submit', async () => {
    api.createTransaction.mockRejectedValueOnce(
      new TransactionApiError('SELL proceeds must be greater than zero after fees', {})
    );
    const { container } = renderWithRouter(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'SELL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '10' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '1' } });
    fireEvent.change(container.querySelector('input[name="fees"]'), { target: { value: '20' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: 'Recommended action' })).not.toBeInTheDocument();
    });
  });

  it('SELL modal shows actual cash received and calculated proceeds preview', () => {
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'SELL' } });
    expect(container.querySelector('input[name="actual_cash_received"]')).toBeInTheDocument();
    expect(screen.getByText(/Leave empty to use calculated proceeds/i)).toBeInTheDocument();
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '10' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '100' } });
    fireEvent.change(container.querySelector('input[name="fees"]'), { target: { value: '2' } });
    expect(screen.getByText(/Calculated proceeds: 998.00 EUR/i)).toBeInTheDocument();
  });

  it('BUY modal hides actual cash received field', () => {
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    expect(container.querySelector('select[name="type"]')).toHaveValue('BUY');
    expect(container.querySelector('input[name="actual_cash_received"]')).not.toBeInTheDocument();
  });

  it('SELL shows withheld preview when actual cash received is lower', () => {
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'SELL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '10' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '100' } });
    fireEvent.change(container.querySelector('input[name="fees"]'), { target: { value: '2' } });
    fireEvent.change(container.querySelector('input[name="actual_cash_received"]'), {
      target: { value: '930' },
    });
    expect(
      screen.getByText(/Tax withheld \/ broker adjustment: 68.00 EUR/i)
    ).toBeInTheDocument();
  });

  it('submit SELL sends actual_cash_received and settlement_note', async () => {
    api.createTransaction.mockResolvedValueOnce({});
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'SELL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '10' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '100' } });
    fireEvent.change(container.querySelector('input[name="fees"]'), { target: { value: '2' } });
    fireEvent.change(container.querySelector('input[name="actual_cash_received"]'), {
      target: { value: '930' },
    });
    fireEvent.change(container.querySelector('input[name="settlement_note"]'), {
      target: { value: 'CGT' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(api.createTransaction).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'SELL',
          actual_cash_received: 930,
          settlement_note: 'CGT',
        })
      );
    });
  });

  it('edit SELL loads actual_cash_received and settlement_note', () => {
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal
          isOpen
          onClose={vi.fn()}
          onSuccess={vi.fn()}
          initialData={{
            id: 9,
            asset_symbol: 'AAPL',
            date: '2026-06-01',
            type: 'SELL',
            quantity: 10,
            price_per_share: 100,
            currency: 'EUR',
            fees: 2,
            actual_cash_received: 930,
            settlement_note: 'Withheld',
            portfolio_id: 1,
          }}
        />
      </PortfolioProvider>
    );
    expect(container.querySelector('input[name="actual_cash_received"]')).toHaveValue(930);
    expect(container.querySelector('input[name="settlement_note"]')).toHaveValue('Withheld');
    expect(screen.getByText(/Tax withheld \/ broker adjustment: 68.00 EUR/i)).toBeInTheDocument();
  });

  it('SELL shows released withheld tax when actual cash received is higher', () => {
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'SELL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '60' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), {
      target: { value: '213.65' },
    });
    fireEvent.change(container.querySelector('input[name="fees"]'), { target: { value: '0' } });
    fireEvent.change(container.querySelector('input[name="actual_cash_received"]'), {
      target: { value: '13755.32' },
    });
    expect(screen.getByText(/Calculated proceeds: 12819.00 EUR/i)).toBeInTheDocument();
    expect(screen.getByText(/Withheld tax released: 936.32 EUR/i)).toBeInTheDocument();
  });

  it('submit SELL sends actual cash above calculated proceeds', async () => {
    api.createTransaction.mockResolvedValueOnce({});
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'ADBE' } });
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'SELL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '60' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), {
      target: { value: '213.65' },
    });
    fireEvent.change(container.querySelector('input[name="fees"]'), { target: { value: '0' } });
    fireEvent.change(container.querySelector('input[name="actual_cash_received"]'), {
      target: { value: '13755.32' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(api.createTransaction).toHaveBeenCalledWith(
        expect.objectContaining({
          asset_symbol: 'ADBE',
          type: 'SELL',
          quantity: 60,
          price_per_share: 213.65,
          actual_cash_received: 13755.32,
        })
      );
    });
  });

  it('successful stock SELL does not show shortfall', async () => {
    api.createTransaction.mockResolvedValueOnce({});
    const onClose = vi.fn();
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={onClose} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), { target: { value: 'AAPL' } });
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'SELL' } });
    fireEvent.change(container.querySelector('input[name="quantity"]'), { target: { value: '1' } });
    fireEvent.change(container.querySelector('input[name="price_per_share"]'), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
    expect(screen.queryByText(/Shortfall:/)).not.toBeInTheDocument();
  });

  it('DIVIDEND asks for gross and tax and submits net inputs', async () => {
    api.createTransaction.mockResolvedValueOnce({});
    const { container } = render(
      <PortfolioProvider initialPortfolios={portfolios} disableFetch>
        <TransactionModal isOpen onClose={vi.fn()} onSuccess={vi.fn()} />
      </PortfolioProvider>
    );
    fireEvent.change(container.querySelector('input[name="asset_symbol"]'), {
      target: { value: 'AAPL' },
    });
    fireEvent.change(container.querySelector('select[name="type"]'), {
      target: { value: 'DIVIDEND' },
    });
    expect(container.querySelector('input[name="quantity"]')).toBeNull();
    fireEvent.change(container.querySelector('input[name="dividend_gross"]'), {
      target: { value: '25' },
    });
    fireEvent.change(container.querySelector('input[name="dividend_tax_withheld"]'), {
      target: { value: '6.6' },
    });
    expect(screen.getByText(/Net cash: 18.40 EUR/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(api.createTransaction).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'DIVIDEND',
          asset_symbol: 'AAPL',
          dividend_gross: 25,
          dividend_tax_withheld: 6.6,
          quantity: 0,
          price_per_share: 0,
          fees: 0,
        })
      );
    });
  });
});
