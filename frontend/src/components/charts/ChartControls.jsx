/** Optional grouped chart controls row (metric/range/benchmark selectors). */
export default function ChartControls({ children, className = '', ariaLabel = 'Chart controls' }) {
  if (!children) return null;

  return (
    <div className={['ui-chart-controls', className].filter(Boolean).join(' ')} aria-label={ariaLabel}>
      {children}
    </div>
  );
}
