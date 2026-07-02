import { Link } from 'react-router-dom';
import { MetricCard } from '../components/ui';
import './Landing.css';

const WHY_POINTS = [
  'Account balances alone do not explain wealth.',
  'Return without risk is incomplete.',
  'Cash-flow timing changes how performance should be read.',
  'Concentration and drawdowns need clear visibility.',
  'Investors need independent clarity before making decisions.',
];

const SIMPLIFY_CARDS = [
  {
    title: 'Portfolio value and invested capital',
    text: 'See total value, capital deployed, and how they relate across your holdings.',
  },
  {
    title: 'XIRR, TWROR, and cumulative return',
    text: 'Compare return measures that respect cash-flow timing and portfolio growth.',
  },
  {
    title: 'Risk, volatility, and drawdowns',
    text: 'Pair performance with volatility, downside, and drawdown context.',
  },
  {
    title: 'Allocation and concentration',
    text: 'Understand how capital is spread across asset classes and positions.',
  },
  {
    title: 'Stocks and mutual funds',
    text: 'Track equities and mutual funds in one structured portfolio view.',
  },
  {
    title: 'Cached market data refresh workflow',
    text: 'Prices and FX are synced on demand — dashboards read from cached data, not live calls.',
  },
];

function DashboardPreview() {
  return (
    <div className="landing-preview" aria-hidden="true">
      <div className="landing-preview__chrome">
        <span className="landing-preview__dot" />
        <span className="landing-preview__dot" />
        <span className="landing-preview__dot" />
        <span className="landing-preview__chrome-label">Portfolio overview</span>
      </div>
      <div className="landing-preview__body">
        <div className="landing-preview__kpis">
          <MetricCard
            size="compact"
            label="Current value"
            value="€ 1,284,500"
            tone="neutral"
          />
          <MetricCard
            size="compact"
            label="Total invested"
            value="€ 980,200"
            tone="neutral"
          />
          <MetricCard
            size="compact"
            label="XIRR"
            value="11.4%"
            tone="positive"
            helperText="Full scope"
          />
          <MetricCard
            size="compact"
            label="Max drawdown"
            value="−8.2%"
            tone="negative"
          />
        </div>
        <div className="landing-preview__chart">
          <div className="landing-preview__chart-header">
            <span>Portfolio value</span>
            <span className="landing-preview__chart-range">1Y</span>
          </div>
          <svg className="landing-preview__chart-svg" viewBox="0 0 320 120" preserveAspectRatio="none">
            <defs>
              <linearGradient id="landing-chart-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.22" />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path
              className="landing-preview__chart-area"
              d="M0,88 L40,72 L80,76 L120,58 L160,64 L200,42 L240,48 L280,28 L320,22 L320,120 L0,120 Z"
              fill="url(#landing-chart-fill)"
            />
            <polyline
              className="landing-preview__chart-line"
              points="0,88 40,72 80,76 120,58 160,64 200,42 240,48 280,28 320,22"
            />
          </svg>
        </div>
      </div>
    </div>
  );
}

export default function Landing() {
  return (
    <div className="landing-page">
      <header className="landing-header">
        <div className="landing-header__inner">
          <div className="landing-brand">
            <span className="landing-brand__name">KPulla</span>
            <span className="landing-brand__subtitle">Portfolio Insight</span>
          </div>
          <nav className="landing-header__nav" aria-label="Public navigation">
            <Link to="/login" className="landing-header__login">
              Login
            </Link>
          </nav>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero" aria-labelledby="landing-hero-heading">
          <div className="landing-hero__copy">
            <p className="landing-eyebrow">Personal wealth intelligence</p>
            <h1 id="landing-hero-heading" className="landing-hero__headline">
              Wealth is easier to build when it is clearly understood.
            </h1>
            <p className="landing-hero__subhead">
              KPulla brings transactions, holdings, market values, cash flows, returns, risk, and
              allocation into one calm portfolio dashboard — so serious investors can understand
              their wealth without spreadsheets.
            </p>
            <div className="landing-hero__cta">
              <Link to="/login" className="ui-btn ui-btn--primary landing-hero__cta-btn">
                Login to Dashboard
              </Link>
            </div>
          </div>
          <DashboardPreview />
        </section>

        <section className="landing-section" aria-labelledby="landing-story-heading">
          <p className="landing-section__eyebrow">The Story So Far</p>
          <h2 id="landing-story-heading" className="landing-section__title">
            Built for investors who want clarity
          </h2>
          <p className="landing-section__body">
            KPulla was created for investors who want more than scattered account balances, broker
            statements, and spreadsheet calculations. It brings transactions, holdings, market
            values, cash flows, returns, risk, and allocation into one calm portfolio dashboard.
          </p>
        </section>

        <section className="landing-section landing-section--panel" aria-labelledby="landing-snapshot-heading">
          <p className="landing-section__eyebrow">A Quick Snapshot</p>
          <h2 id="landing-snapshot-heading" className="landing-section__title">
            Simplifying wealth management for serious personal investors.
          </h2>
          <p className="landing-section__body">
            KPulla turns investment activity into structured insight across portfolio value, invested
            capital, realized and unrealized gains, XIRR, TWROR, cumulative return, drawdowns,
            allocation, and asset-level performance.
          </p>
        </section>

        <section className="landing-section" aria-labelledby="landing-why-heading">
          <p className="landing-section__eyebrow">Why wealth management matters</p>
          <h2 id="landing-why-heading" className="landing-section__title">
            Numbers need context to guide decisions
          </h2>
          <ul className="landing-list">
            {WHY_POINTS.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </section>

        <section className="landing-section" aria-labelledby="landing-simplify-heading">
          <p className="landing-section__eyebrow">What KPulla simplifies</p>
          <h2 id="landing-simplify-heading" className="landing-section__title">
            One workspace for the metrics that matter
          </h2>
          <div className="landing-card-grid">
            {SIMPLIFY_CARDS.map((card) => (
              <article key={card.title} className="landing-card">
                <h3 className="landing-card__title">{card.title}</h3>
                <p className="landing-card__text">{card.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-section landing-section--philosophy" aria-labelledby="landing-philosophy-heading">
          <p className="landing-section__eyebrow">Philosophy</p>
          <h2 id="landing-philosophy-heading" className="landing-section__title">
            Independent clarity over your wealth
          </h2>
          <p className="landing-section__body landing-section__body--lead">
            We believe every investor should have independent clarity over their wealth. A portfolio
            is not only a list of assets. It is a living record of decisions, cash flows, market
            movement, risk, and time. KPulla helps simplify this complexity so better judgment
            becomes possible.
          </p>
        </section>

        <section className="landing-cta" aria-labelledby="landing-final-cta-heading">
          <div className="landing-cta__inner">
            <h2 id="landing-final-cta-heading" className="landing-cta__title">
              Don&apos;t manage wealth through scattered views.
            </h2>
            <p className="landing-cta__text">
              Bring your portfolio into one calm, measurable, and decision-ready workspace.
            </p>
            <Link to="/login" className="ui-btn ui-btn--primary landing-cta__btn">
              Login to Dashboard
            </Link>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <p className="landing-footer__copy">KPulla — Portfolio Insight</p>
      </footer>
    </div>
  );
}
