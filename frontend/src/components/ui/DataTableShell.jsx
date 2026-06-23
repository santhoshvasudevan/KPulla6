import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import LoadingState from './LoadingState';
import SectionHeader from './SectionHeader';

export default function DataTableShell({
  title,
  subtitle,
  actions,
  children,
  empty = false,
  emptyTitle = 'No records',
  emptyDescription,
  emptyAction,
  loading = false,
  loadingMessage = 'Loading…',
  error,
  errorTitle = 'Unable to load data',
  onRetry,
  compact = false,
  dense = false,
  className = '',
}) {
  const classes = [
    'ui-data-table-shell',
    compact ? 'ui-data-table-shell--compact' : '',
    dense ? 'ui-data-table-shell--dense' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');
  const showHeader = title || subtitle || actions;

  let body = children;
  if (loading) {
    body = <LoadingState message={loadingMessage} variant="skeleton" />;
  } else if (error) {
    body = <ErrorState title={errorTitle} message={error} onRetry={onRetry} />;
  } else if (empty) {
    body = <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />;
  }

  return (
    <section className={classes}>
      {showHeader ? (
        <SectionHeader title={title} subtitle={subtitle} actions={actions} className="ui-data-table-shell__header" />
      ) : null}
      <div className="ui-data-table-shell__scroller">{body}</div>
    </section>
  );
}
