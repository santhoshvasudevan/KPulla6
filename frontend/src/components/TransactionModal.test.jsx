import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
    createCashDeposit: vi.fn(),
    createCashWithdrawal: vi.fn(),
    fetchPortfolios: vi.fn(),
  };
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
    fireEvent.change(container.querySelector('input[name="nav"]'), { target: { value: '42.5' } });
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
    fireEvent.change(container.querySelector('input[name="nav"]'), { target: { value: '42.5' } });
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
    fireEvent.change(container.querySelector('input[name="nav"]'), { target: { value: '42.5' } });
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
});
