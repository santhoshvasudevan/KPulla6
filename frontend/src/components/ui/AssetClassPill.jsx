const ASSET_CLASS_LABELS = {
  stock: 'Stock',
  mutualFund: 'Mutual Fund',
  fixedDeposit: 'Fixed Deposit',
  cash: 'Cash',
  benchmark: 'Benchmark',
  neutral: 'Asset',
};

export default function AssetClassPill({ variant = 'neutral', label, className = '' }) {
  const text = label ?? ASSET_CLASS_LABELS[variant] ?? variant;
  const classes = ['ui-asset-pill', `ui-asset-pill--${variant}`, className].filter(Boolean).join(' ');

  return (
    <span className={classes} aria-label={`Asset class: ${text}`}>
      {text}
    </span>
  );
}
