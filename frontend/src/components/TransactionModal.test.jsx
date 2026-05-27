import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import TransactionModal from './TransactionModal';
import * as api from '../api';
import { PortfolioProvider } from '../portfolioContext';

vi.mock('../api', () => ({
  createTransaction: vi.fn(),
  updateTransaction: vi.fn(),
  fetchPortfolios: vi.fn(),
}));

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

  it('defaults asset type to STOCK', () => {
    const { container } = renderModal();
    expect(screen.getByLabelText('asset type')).toHaveValue('STOCK');
    expect(container.querySelector('input[name="asset_symbol"]')).toBeInTheDocument();
  });

  it('selecting STOCK_SPLIT changes form layout', () => {
    const { container } = renderModal();
    fireEvent.change(container.querySelector('select[name="type"]'), { target: { value: 'STOCK_SPLIT' } });
    expect(container.querySelector('input[name="split_from"]')).toBeInTheDocument();
    expect(container.querySelector('input[name="split_to"]')).toBeInTheDocument();
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
    const { container } = renderModal();
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

  it('switches to mutual fund form mode', () => {
    const { container } = renderModal();
    fireEvent.change(screen.getByLabelText('asset type'), { target: { value: 'MUTUAL_FUND' } });
    expect(container.querySelector('input[name="scheme_code"]')).toBeInTheDocument();
    expect(container.querySelector('input[name="scheme_name"]')).toBeInTheDocument();
    expect(container.querySelector('input[name="folio_number"]')).toBeInTheDocument();
    expect(container.querySelector('input[name="nav"]')).toBeInTheDocument();
    expect(container.querySelector('input[name="units_allotted"]')).toBeInTheDocument();
    expect(container.querySelector('input[name="asset_symbol"]')).not.toBeInTheDocument();
  });

  it('renders MF type options as BUY and SELL only', () => {
    renderModal();
    fireEvent.change(screen.getByLabelText('asset type'), { target: { value: 'MUTUAL_FUND' } });
    const typeSelect = document.querySelector('select[name="type"]');
    const options = Array.from(typeSelect.options).map((o) => o.value);
    expect(options).toEqual(['BUY', 'SELL']);
  });

  it('submits MF create with backend field names', async () => {
    api.createTransaction.mockResolvedValueOnce({});
    const { container } = renderModal();
    fireEvent.change(screen.getByLabelText('asset type'), { target: { value: 'MUTUAL_FUND' } });
    fireEvent.change(container.querySelector('input[name="scheme_code"]'), { target: { value: '120503' } });
    fireEvent.change(container.querySelector('input[name="scheme_name"]'), { target: { value: 'Test Fund' } });
    fireEvent.change(container.querySelector('input[name="folio_number"]'), { target: { value: 'F1' } });
    fireEvent.change(container.querySelector('input[name="investment_date"]'), { target: { value: '2026-03-10' } });
    fireEvent.change(container.querySelector('input[name="nav_date"]'), { target: { value: '2026-03-15' } });
    fireEvent.change(container.querySelector('input[name="nav"]'), { target: { value: '42.5' } });
    fireEvent.change(container.querySelector('input[name="units_allotted"]'), { target: { value: '100' } });
    fireEvent.change(container.querySelector('input[name="paid_value"]'), { target: { value: '4255' } });
    fireEvent.change(container.querySelector('input[name="market_value"]'), { target: { value: '4250' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(api.createTransaction).toHaveBeenCalledWith({
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
      });
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
    expect(screen.getByLabelText('asset type')).toBeDisabled();
    expect(screen.getByDisplayValue('120503')).toBeDisabled();
    expect(screen.getByDisplayValue('Test Fund')).toBeInTheDocument();
    expect(screen.getByText('NAV not in cache')).toBeInTheDocument();

    fireEvent.change(container.querySelector('input[name="paid_value"]'), { target: { value: '4300' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(api.updateTransaction).toHaveBeenCalledWith(
        99,
        expect.objectContaining({
          asset_type: 'MUTUAL_FUND',
          paid_value: 4300,
          scheme_code: '120503',
        })
      );
    });
  });

  it('shows backend validation errors', async () => {
    api.createTransaction.mockRejectedValueOnce(new Error('folio_number: This field may not be blank.'));
    const { container } = renderModal();
    fireEvent.change(screen.getByLabelText('asset type'), { target: { value: 'MUTUAL_FUND' } });
    fireEvent.change(container.querySelector('input[name="scheme_code"]'), { target: { value: '120503' } });
    fireEvent.change(container.querySelector('input[name="scheme_name"]'), { target: { value: 'Test Fund' } });
    fireEvent.change(container.querySelector('input[name="folio_number"]'), { target: { value: 'F1' } });
    fireEvent.change(container.querySelector('input[name="investment_date"]'), { target: { value: '2026-03-10' } });
    fireEvent.change(container.querySelector('input[name="nav_date"]'), { target: { value: '2026-03-15' } });
    fireEvent.change(container.querySelector('input[name="nav"]'), { target: { value: '42.5' } });
    fireEvent.change(container.querySelector('input[name="units_allotted"]'), { target: { value: '100' } });
    fireEvent.change(container.querySelector('input[name="paid_value"]'), { target: { value: '4255' } });
    fireEvent.change(container.querySelector('input[name="market_value"]'), { target: { value: '4250' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByText('folio_number: This field may not be blank.')).toBeInTheDocument();
    });
  });
});
