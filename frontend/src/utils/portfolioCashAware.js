/** Payload to enable cash-aware mode via PUT /api/v1/portfolios/{id}. */
export function buildCashAwareEnablePayload(portfolio) {
  return {
    name: portfolio.name,
    description: portfolio.description ?? null,
    base_currency: portfolio.base_currency || 'EUR',
    is_active: portfolio.is_active !== false,
    cash_aware_enabled: true,
  };
}

export const CASH_AWARE_ON_MESSAGE =
  'Cash-aware mode is on. Purchases require available cash.';

export const CASH_AWARE_OFF_MESSAGE =
  'Cash-aware mode is off. Purchases can be recorded without cash balance checks.';

export const CASH_AWARE_ALL_SCOPE_NOTE =
  'Cash-aware mode is configured per portfolio. Select a single portfolio to enable it.';

export const CASH_AWARE_ENABLE_CONFIRM =
  'After enabling cash-aware mode, new purchases in this portfolio require available cash. Existing transactions are not changed.';
