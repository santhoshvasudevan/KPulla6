import { WarningBanner } from '../ui';

function warningSeverity(message) {
  const text = String(message || '').toLowerCase();
  if (text.includes('compare api metrics')) {
    return 'info';
  }
  if (
    text.includes('split-adjusted') ||
    text.includes('unreliable') ||
    text.includes('insufficient') ||
    text.includes('missing') ||
    text.includes('unavailable') ||
    text.includes('fx') ||
    text.includes('nav') ||
    text.includes('price') ||
    text.includes('benchmark')
  ) {
    return 'warning';
  }
  return 'info';
}

export default function MetricSheetWarnings({ warnings = [], className = '' }) {
  if (!warnings?.length) return null;

  return (
    <div className={['metric-sheet__warnings', className].filter(Boolean).join(' ')}>
      {warnings.map((message, index) => (
        <WarningBanner
          key={`${index}-${String(message).slice(0, 32)}`}
          severity={warningSeverity(message)}
          message={message}
        />
      ))}
    </div>
  );
}
