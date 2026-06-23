export default function SectionHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  headingLevel = 3,
  className = '',
}) {
  const Heading = `h${Math.min(Math.max(Number(headingLevel) || 3, 1), 6)}`;
  const classes = ['ui-section-header', className].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      <div className="ui-section-header__copy">
        {eyebrow ? <p className="ui-section-header__eyebrow">{eyebrow}</p> : null}
        {title ? <Heading className="ui-section-header__title">{title}</Heading> : null}
        {subtitle ? <p className="ui-section-header__subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="ui-section-header__actions">{actions}</div> : null}
    </div>
  );
}
