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
});
