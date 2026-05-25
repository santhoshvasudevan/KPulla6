export default function LoadingState({ message = 'Loading…', variant = 'spinner', className = '' }) {
  const classes = ['ui-loading-state', className].filter(Boolean).join(' ');

  return (
    <div className={classes} role="status" aria-live="polite" aria-busy="true">
      {variant === 'skeleton' ? (
        <div className="ui-loading-state__skeleton" aria-hidden="true">
          <div className="ui-loading-state__skeleton-line" />
          <div className="ui-loading-state__skeleton-line ui-loading-state__skeleton-line--short" />
          <div className="ui-loading-state__skeleton-line" />
        </div>
      ) : (
        <div className="ui-loading-state__spinner" aria-hidden="true" />
      )}
      <p className="ui-loading-state__message">{message}</p>
    </div>
  );
}
