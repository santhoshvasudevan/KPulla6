import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';

vi.mock('./api', () => ({
  fetchPortfolios: vi.fn().mockResolvedValue([]),
  getSettings: vi.fn().mockResolvedValue({ display_currency: 'EUR', tax_rate_percentage: 26.375 }),
  updateSettings: vi.fn(),
  invalidateDashboardSummaryCache: vi.fn(),
  fetchDashboardSummary: vi.fn().mockResolvedValue({
    total_invested: 0,
    current_value: 0,
    realized_pl: 0,
    unrealized_pl: 0,
    total_pl: 0,
    xirr: null,
    display_currency: 'EUR',
    fx_status: 'ok',
  }),
  fetchPortfolioPerformance: vi.fn().mockResolvedValue([]),
  fetchBenchmarkIndices: vi.fn().mockResolvedValue([]),
  getPortfolioMetricSheet: vi.fn().mockResolvedValue({
    metrics: {
      return: { cumulative_return: null, cagr: null, xirr: null, xirr_scope: 'full_scope', twror: null },
      risk: { volatility_annualized: null, downside_deviation: null, sharpe_ratio: null, sortino_ratio: null },
      drawdown: { max_drawdown: null, longest_drawdown_days: null, calmar_ratio: null },
      periods: { best_day: null, worst_day: null, win_rate: null, average_daily_return: null },
    },
    warnings: [],
  }),
}));

describe('App', () => {
  it('renders layout navigation', async () => {
    render(<App />);
    expect(screen.getByText('Portfolio Insight')).toBeTruthy();
    expect(await screen.findByText('Dashboard')).toBeTruthy();
    expect(screen.getByText('Transactions')).toBeTruthy();
    expect(screen.getByText('Assets')).toBeTruthy();
  });
});
