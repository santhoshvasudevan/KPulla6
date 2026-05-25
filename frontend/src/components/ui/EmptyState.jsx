export default function EmptyState({ title, description, action, icon, className = '' }) {
  const classes = ['ui-empty-state', className].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      {icon ? <div className="ui-empty-state__icon">{icon}</div> : null}
      {title ? <h3 className="ui-empty-state__title">{title}</h3> : null}
      {description ? <p className="ui-empty-state__description">{description}</p> : null}
      {action ? <div className="ui-empty-state__action">{action}</div> : null}
    </div>
  );
}
