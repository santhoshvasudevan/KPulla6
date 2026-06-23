export default function SectionCard({
  title,
  subtitle,
  actions,
  children,
  className = '',
  compact = false,
  id,
}) {
  const classes = ['ui-section-card', compact ? 'ui-section-card--compact' : '', className]
    .filter(Boolean)
    .join(' ');

  const showHeader = title || subtitle || actions;

  return (
    <section className={classes} id={id}>
      {showHeader ? (
        <div className="ui-section-card__header">
          <div>
            {title ? <h3 className="ui-section-card__title">{title}</h3> : null}
            {subtitle ? <p className="ui-section-card__subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="ui-section-card__actions">{actions}</div> : null}
        </div>
      ) : null}
      <div className="ui-section-card__body">{children}</div>
    </section>
  );
}
