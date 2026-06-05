import { holdingSymbolLabel } from './transactionDisplay';

/** Open/active holding for compare picker preference. */
export function isActiveHolding(h) {
  return h.holding_status !== 'closed' && Number(h.quantity || 0) > 0;
}

/**
 * Unique asset symbols for Compare pickers: active holdings first, closed labeled.
 * When both active and closed rows exist for a symbol, the active row wins.
 */
export function buildCompareAssetOptions(holdings) {
  const bySymbol = new Map();

  for (const h of holdings || []) {
    if (h.is_cash || h.asset_type === 'CASH') continue;
    const sym = h.asset_symbol;
    if (!sym) continue;

    const active = isActiveHolding(h);
    const existing = bySymbol.get(sym);
    if (!existing || (active && !existing.active)) {
      bySymbol.set(sym, { symbol: sym, active, holding: h });
    }
  }

  const options = [...bySymbol.values()].map(({ symbol, active, holding }) => {
    const base = holdingSymbolLabel(holding) || symbol;
    const label = active ? base : `${base} (closed)`;
    return { symbol, label, active };
  });

  options.sort((a, b) => {
    if (a.active !== b.active) return a.active ? -1 : 1;
    return a.label.localeCompare(b.label);
  });

  return options;
}
