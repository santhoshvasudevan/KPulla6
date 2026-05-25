export default function PageHeader({ title, subtitle, eyebrow, breadcrumb, actions }) {
  return (
    <header className="ui-page-header">
      {breadcrumb ? (
        <nav className="ui-page-header__breadcrumb" aria-label="Breadcrumb">
          {breadcrumb}
        </nav>
      ) : null}
      {eyebrow ? <p className="ui-page-header__eyebrow">{eyebrow}</p> : null}
      <div className="ui-page-header__row">
        <div className="ui-page-header__main">
          {title ? <h2 className="ui-page-header__title">{title}</h2> : null}
          {subtitle ? <p className="ui-page-header__subtitle">{subtitle}</p> : null}
        </div>
        {actions ? <div className="ui-page-header__actions">{actions}</div> : null}
      </div>
    </header>
  );
}
