import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import Layout from './Layout';
import { PortfolioProvider } from '../portfolioContext';
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

    // Check for navigation links
    expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/transactions/i)).toBeInTheDocument();
    expect(screen.getByText(/assets/i)).toBeInTheDocument();
    expect(screen.getByText(/settings/i)).toBeInTheDocument();

    // Portfolio selector
    expect(screen.getByText(/portfolio view/i)).toBeInTheDocument();
    expect(screen.getByLabelText('portfolio-view')).toBeInTheDocument();

    // Display currency selector
    expect(screen.getByText(/display currency/i)).toBeInTheDocument();
    expect(screen.getByLabelText('display-currency')).toBeInTheDocument();

    // Check if child outlet is rendered
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });
});
