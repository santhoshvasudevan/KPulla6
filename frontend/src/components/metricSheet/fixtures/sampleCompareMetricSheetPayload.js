/** Fixture for Compare Metric Sheet tests — values are display-only from API. */

const sampleCompareMetricSheetPayload = {
  range: {
    code: '1Y',
    start: '2025-05-30',
    end: '2026-05-30',
  },
  currency: 'EUR',
  common_start_date: '2025-06-01',
  common_end_date: '2026-05-30',
  common_point_count: 252,
  warnings: ['Compare API metrics are computed over common overlapping dates only.'],
  normalized_series: [
    {
      date: '2025-06-01',
      values: { 'asset:AAPL': 0, 'asset:MSFT': 0 },
    },
    {
      date: '2026-05-30',
      values: { 'asset:AAPL': 0.1234, 'asset:MSFT': 0.0567 },
    },
  ],
  subjects: [
    {
      id: 'asset:AAPL',
      type: 'asset',
      asset_symbol: 'AAPL',
      name: 'Apple Inc.',
      folio_number: null,
      warnings: ['Subject-specific warning for AAPL.'],
      metrics: {
        return: {
          cumulative_return: 0.1234,
          cagr: 0.12,
          twror: 0.11,
          xirr: 0.15,
          xirr_scope: 'full_scope',
        },
        risk: {
          volatility_annualized: 0.2,
          sharpe_ratio: 1.1,
          sortino_ratio: 1.3,
        },
        drawdown: {
          max_drawdown: -0.08,
          calmar_ratio: 1.5,
        },
      },
      periodic_returns: {
        monthly: [{ period: '2026-01', return: 0.03 }],
        yearly: [
          { period: '2025', return: 0.12 },
          { period: '2026', return: 0.05 },
        ],
      },
      drawdown_periods: {
        worst: [
          {
            start_date: '2025-06-01',
            trough_date: '2025-07-01',
            recovery_date: '2025-08-01',
            drawdown: -0.15,
            days_to_trough: 30,
            days_to_recovery: 61,
            recovered: true,
          },
        ],
      },
      benchmark: {
        symbol: '^GSPC',
        paired_count: 250,
        metrics: {
          beta: 1.05,
          alpha: 0.02,
          correlation: 0.88,
          information_ratio: 0.4,
          tracking_error: 0.03,
        },
      },
    },
    {
      id: 'asset:MSFT',
      type: 'asset',
      asset_symbol: 'MSFT',
      name: 'Microsoft Corp.',
      folio_number: null,
      warnings: [],
      metrics: {
        return: {
          cumulative_return: 0.0567,
          cagr: 0.05,
          twror: 0.04,
          xirr: null,
          xirr_scope: null,
        },
        risk: {
          volatility_annualized: 0.18,
          sharpe_ratio: 0.9,
          sortino_ratio: 1.0,
        },
        drawdown: {
          max_drawdown: -0.06,
          calmar_ratio: 1.2,
        },
      },
      periodic_returns: {
        monthly: [],
        yearly: [{ period: '2026', return: 0.04 }],
      },
      drawdown_periods: {
        worst: [
          {
            start_date: '2025-08-01',
            trough_date: '2025-09-01',
            recovery_date: null,
            drawdown: -0.08,
            days_to_trough: 31,
            days_to_recovery: null,
            recovered: false,
          },
        ],
      },
      benchmark: {
        symbol: '^GSPC',
        paired_count: 250,
        metrics: {
          beta: 0.95,
          alpha: -0.01,
          correlation: 0.82,
          information_ratio: 0.2,
          tracking_error: 0.04,
        },
      },
    },
  ],
};

export default sampleCompareMetricSheetPayload;
