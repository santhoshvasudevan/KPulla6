import SectionHeader from './SectionHeader';

export default function AppCard({
  eyebrow,
  title,
  subtitle,
  actions,
  children,
  footer,
  className = '',
  compact = false,
  elevated = false,
  as: Component = 'section',
}) {
  const classes = [
    'ui-app-card',
    compact ? 'ui-app-card--compact' : '',
    elevated ? 'ui-app-card--elevated' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');
  const showHeader = eyebrow || title || subtitle || actions;

  return (
    <Component className={classes}>
      {showHeader ? (
        <SectionHeader
          eyebrow={eyebrow}
          title={title}
          subtitle={subtitle}
          actions={actions}
          className="ui-app-card__header"
        />
      ) : null}
      <div className="ui-app-card__body">{children}</div>
      {footer ? <div className="ui-app-card__footer">{footer}</div> : null}
    </Component>
  );
}
