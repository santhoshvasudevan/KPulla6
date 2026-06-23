import { EmptyState, ErrorState, LoadingState } from '../ui';

export function ChartEmptyState({
  title = 'No chart data',
  description,
  action,
  variant = 'card',
  className = '',
}) {
  if (variant === 'inline') {
    return (
      <p className={['ui-chart-empty-state--inline', className].filter(Boolean).join(' ')}>
        {description || title}
      </p>
    );
  }

  return (
    <EmptyState
      title={title}
      description={description}
      action={action}
      className={['ui-chart-empty-state', className].filter(Boolean).join(' ')}
    />
  );
}

export function ChartLoadingState({
  message = 'Loading chart…',
  variant = 'skeleton',
  className = '',
}) {
  return (
    <LoadingState
      message={message}
      variant={variant}
      className={['ui-chart-loading-state', className].filter(Boolean).join(' ')}
    />
  );
}

export function ChartErrorState({
  title = 'Chart unavailable',
  message,
  onRetry,
  action,
  className = '',
}) {
  return (
    <ErrorState
      title={title}
      message={message}
      onRetry={onRetry}
      action={action}
      className={['ui-chart-error-state', className].filter(Boolean).join(' ')}
    />
  );
}

export function ChartPartialState({ message, className = '' }) {
  if (!message) return null;
  return (
    <p className={['ui-chart-partial-state', className].filter(Boolean).join(' ')} role="status">
      {message}
    </p>
  );
}
