import Button from './Button';

export default function ErrorState({
  title = 'Error',
  message,
  action,
  onRetry,
  className = '',
}) {
  const classes = ['ui-error-state', className].filter(Boolean).join(' ');
  const actionNode =
    action ??
    (onRetry ? (
      <Button variant="secondary" onClick={onRetry}>
        Try again
      </Button>
    ) : null);

  return (
    <div className={classes} role="alert">
      {title ? <h3 className="ui-error-state__title">{title}</h3> : null}
      {message ? <p className="ui-error-state__message">{message}</p> : null}
      {actionNode}
    </div>
  );
}
