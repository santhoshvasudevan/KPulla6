import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Landing from './Landing';

vi.mock('../api', () => ({
  fetchDashboardSummary: vi.fn(),
  fetchPortfolioPerformance: vi.fn(),
  fetchPortfolios: vi.fn(),
  getSettings: vi.fn(),
  fetchCurrentUser: vi.fn(),
}));

import * as api from '../api';

describe('Landing page', () => {
  it('renders the hero headline for public visitors', () => {
    render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('heading', {
        name: /wealth is easier to build when it is clearly understood/i,
      })
    ).toBeInTheDocument();
  });

  it('links Login actions to /login', () => {
    render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>
    );

    const loginLinks = screen.getAllByRole('link', { name: /login/i });
    expect(loginLinks.length).toBeGreaterThanOrEqual(2);
    loginLinks.forEach((link) => {
      expect(link).toHaveAttribute('href', '/login');
    });

    const dashboardCtas = screen.getAllByRole('link', { name: /login to dashboard/i });
    dashboardCtas.forEach((link) => {
      expect(link).toHaveAttribute('href', '/login');
    });
  });

  it('does not call portfolio APIs', () => {
    render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>
    );

    expect(api.fetchDashboardSummary).not.toHaveBeenCalled();
    expect(api.fetchPortfolioPerformance).not.toHaveBeenCalled();
    expect(api.fetchPortfolios).not.toHaveBeenCalled();
    expect(api.getSettings).not.toHaveBeenCalled();
    expect(api.fetchCurrentUser).not.toHaveBeenCalled();
  });
});
