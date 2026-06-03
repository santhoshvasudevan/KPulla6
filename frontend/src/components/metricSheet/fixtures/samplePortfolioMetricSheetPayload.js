/** Test fixture mirroring GET /api/v1/analytics/performance-metrics (fractional metrics). */
export default {
  subject: {
    type: 'portfolio',
    portfolio_scope: 'all',
    portfolio_id: null,
    name: 'All Portfolios',
  },
  range: {
    code: '1Y',
    start: '2025-03-15',
    end: '2026-03-15',
  },
  currency: 'EUR',
  metrics: {
    return: {
      cumulative_return: 0.1234,
      cagr: 0.118,
      xirr: 0.142,
      xirr_scope: 'full_scope',
      twror: 0.121,
    },
    risk: {
      volatility_annualized: 0.182,
      downside_deviation: 0.091,
      sharpe_ratio: 1.24,
      sortino_ratio: 1.55,
    },
    drawdown: {
      max_drawdown: -0.082,
      longest_drawdown_days: 42,
      calmar_ratio: 1.44,
    },
    periods: {
      best_day: 0.032,
      worst_day: -0.028,
      win_rate: 0.55,
      average_daily_return: 0.0008,
    },
  },
  benchmark: {
    symbol: '^GSPC',
    paired_count: 252,
    metrics: {
      correlation: 0.78,
      beta: 1.12,
      alpha: 0.021,
      active_return: 0.035,
      tracking_error: 0.048,
      information_ratio: 0.73,
      treynor_ratio: 0.09,
    },
  },
  periodic_returns: {
    monthly: [
      { period: '2026-01', return: 0.021 },
      { period: '2026-02', return: -0.012 },
    ],
    yearly: [{ period: '2025', return: 0.143 }],
  },
  drawdown_periods: {
    worst: [
      {
        rank: 1,
        start_date: '2025-06-10',
        trough_date: '2025-07-05',
        recovery_date: '2025-08-20',
        drawdown: -0.182,
        days_to_trough: 25,
        days_to_recovery: 71,
        recovered: true,
      },
      {
        rank: 2,
        start_date: '2025-11-01',
        trough_date: '2025-12-15',
        recovery_date: null,
        drawdown: -0.09,
        days_to_trough: 44,
        days_to_recovery: null,
        recovered: false,
      },
    ],
  },
  drawdown_series: [
    { date: '2025-06-10', drawdown: 0 },
    { date: '2025-07-05', drawdown: -0.182 },
    { date: '2025-08-20', drawdown: 0 },
    { date: '2025-11-01', drawdown: 0 },
    { date: '2025-12-15', drawdown: -0.09 },
    { date: '2026-03-15', drawdown: -0.09 },
  ],
  warnings: [
    'Cached historical prices for AAPL may not be split-adjusted; Metric Sheet returns around stock splits may be unreliable.',
  ],
};
