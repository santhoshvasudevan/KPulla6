import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import Layout from './Layout';
import { PortfolioProvider, usePortfolio } from '../portfolioContext';
import * as api from '../api';

vi.mock('../api', () => ({
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
}));

describe('Layout component', () => {
  it('renders navigation links and outlet', () => {
    api.fetchPortfolios.mockResolvedValueOnce([]);
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    render(
      <PortfolioProvider>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<div data-testid="child">Child Content</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </PortfolioProvider>
    );

    expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/transactions/i)).toBeInTheDocument();
    expect(screen.getByText(/assets/i)).toBeInTheDocument();
    expect(screen.getByText(/settings/i)).toBeInTheDocument();
    expect(screen.getByText(/portfolio view/i)).toBeInTheDocument();
    expect(screen.getByLabelText('portfolio-view')).toBeInTheDocument();
    expect(screen.getByText(/display currency/i)).toBeInTheDocument();
    expect(screen.getByLabelText('display-currency')).toBeInTheDocument();
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('shows renamed portfolio in selector after reloadPortfolios', async () => {
    api.getSettings.mockResolvedValueOnce({ display_currency: 'EUR' });
    api.fetchPortfolios.mockResolvedValueOnce([
      { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
      { id: 2, name: 'Old Name', is_default: false, is_active: true, base_currency: 'EUR' },
    ]);

    function TestHarness() {
      const { reloadPortfolios } = usePortfolio();
      return (
        <>
          <button type="button" onClick={() => reloadPortfolios()}>
            Reload
          </button>
          <Layout />
        </>
      );
    }

    api.fetchPortfolios.mockResolvedValueOnce([
      { id: 1, name: 'Default Portfolio', is_default: true, is_active: true, base_currency: 'EUR' },
      { id: 2, name: 'Renamed Portfolio', is_default: false, is_active: true, base_currency: 'EUR' },
    ]);

    render(
      <PortfolioProvider>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="/" element={<TestHarness />}>
              <Route index element={<div data-testid="child">Child</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </PortfolioProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('portfolio-view')).toBeInTheDocument();
    });

    expect(screen.getByRole('option', { name: 'Old Name' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Reload' }));

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Renamed Portfolio' })).toBeInTheDocument();
    });
    expect(screen.queryByRole('option', { name: 'Old Name' })).not.toBeInTheDocument();
  });
});
