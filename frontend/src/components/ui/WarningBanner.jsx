const BANNER_ROLES = {
  info: 'status',
  warning: 'alert',
  error: 'alert',
  success: 'status',
};

export default function WarningBanner({
  severity = 'info',
  title,
  message,
  children,
  action,
  className = '',
}) {
  const body = children ?? message;
  const classes = ['ui-banner', `ui-banner--${severity}`, className].filter(Boolean).join(' ');

  return (
    <div className={classes} role={BANNER_ROLES[severity] || 'status'}>
      <div className="ui-banner__content">
        {title ? <p className="ui-banner__title">{title}</p> : null}
        {body ? <p className="ui-banner__message">{body}</p> : null}
      </div>
      {action ? <div className="ui-banner__action">{action}</div> : null}
    </div>
  );
}
