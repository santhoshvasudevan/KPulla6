// Three read-only dashboard directions on /dashboard?variant=A, B or C.
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, ArrowUpRight } from 'lucide-react';
import { CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatCurrency, formatPercent } from '../../utils/formatters';
import './WealthPrototype.css';

const variants = { A: 'Value history', B: 'Allocation explorer', C: 'Portfolio review' };
const palette = ['#178c80', '#648adb', '#cc9149', '#966fae', '#7f9957', '#bf7e86'];
const color = (i) => palette[i % palette.length];
const money = (value, currency) => value == null ? '—' : formatCurrency(value, currency);

function Switcher({ variant, change }) {
  useEffect(() => {
    function onKey(event) {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey ||
          event.target.closest?.('input, textarea, select, [contenteditable], [role="slider"], [role="tablist"]')) return;
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      change(event.key === 'ArrowRight' ? 1 : -1);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [change]);
  return <nav className="wp-switch" aria-label="Prototype designs">
    <button aria-label="Previous design" onClick={() => change(-1)}><ArrowLeft size={18} /></button>
    <span aria-live="polite">{variant} · {variants[variant]}</span>
    <button aria-label="Next design" onClick={() => change(1)}><ArrowRight size={18} /></button>
  </nav>;
}

function Trend({ trend }) {
  return <section className="wp-panel wp-trend">
    <header><div><small>Portfolio performance</small><h2>{trend.label}</h2></div><span>{trend.range}</span></header>
    {trend.controls}
    {trend.data.length > 0 && !trend.loading ? <>
      <div className="wp-chart" role="group" aria-label={trend.label}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={trend.data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--border-subtle)" strokeDasharray="3 5" />
            <XAxis dataKey="date" tickFormatter={trend.dateLabel} minTickGap={36} tickLine={false} axisLine={false} />
            <YAxis tickFormatter={trend.axisLabel} width={55} tickLine={false} axisLine={false} />
            <Tooltip formatter={trend.valueLabel} contentStyle={{ background: 'var(--surface)', borderColor: 'var(--border-strong)' }} />
            {trend.lines.map((l, i) => <Line key={l.dataKey} dataKey={l.dataKey} name={l.name}
              stroke={i === 0 ? 'var(--wp-ink)' : l.stroke} strokeWidth={i === 0 ? 3 : 2}
              strokeDasharray={i ? '5 4' : undefined} dot={trend.data.length === 1} isAnimationActive={false} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {trend.lines.length > 1 && <div className="wp-series">{trend.lines.map((line, i) =>
        <span key={line.dataKey}><i style={{ background: i === 0 ? 'var(--wp-ink)' : line.stroke }} />{line.name}</span>)}</div>}
    </> : !trend.loading && <p>No performance series for this period.</p>}
    {trend.footer}
  </section>;
}

function Mix({ buckets, total, currency, expanded = false }) {
  const [choice, setChoice] = useState('');
  const [hover, setHover] = useState('');
  const selected = buckets.find(b => b.label === (hover || choice));
  const share = b => (100 * Number(b.value) / total).toFixed(1) + '%';
  return <section className="wp-panel wp-mix">
    <header><div><small>Current value</small><h2>Asset allocation</h2></div>
      <Link to="/assets">Assets <ArrowUpRight size={15} /></Link></header>
    {!buckets.length ? <p>No allocation data for this scope.</p> : <div className={expanded ? 'wp-mix-detail' : ''}>
      {expanded ? <div className="wp-ring">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart><Pie data={buckets} dataKey={b => Number(b.value)} nameKey="label" cx="50%" cy="50%"
            innerRadius="66%" outerRadius="92%" stroke="var(--surface)" isAnimationActive={false}
            onMouseEnter={b => setHover(b.label)} onMouseLeave={() => setHover('')} onClick={b => setChoice(b.label)}>
            {buckets.map((b, i) => <Cell key={b.label} fill={color(i)} opacity={selected && b.label !== selected.label ? 0.55 : 1} />)}
          </Pie></PieChart>
        </ResponsiveContainer>
        <div className="wp-ring-label"><small>{selected?.label || 'Allocation'}</small>
          <b>{selected ? share(selected) : '100%'}</b><span>{money(selected ? selected.value : total, currency)}</span></div>
      </div> : <div className="wp-strip" aria-hidden="true">{buckets.map((b,i) =>
        <i key={b.label} style={{ width: share(b), background: color(i) }} />)}</div>}
      <div className="wp-ranks">{buckets.map((b, i) => {
        const row = <><span><i style={{ background: color(i) }} />{b.label}</span><span>{money(b.value, currency)}</span><b>{share(b)}</b></>;
        return expanded ? <button key={b.label} aria-pressed={choice === b.label} onClick={() => setChoice(choice === b.label ? '' : b.label)}>{row}</button>
          : <div key={b.label}>{row}</div>;
      })}</div>
    </div>}
  </section>;
}

function Measurements({ summary: s, currency, detailed = false }) {
  const metrics = [
    ['Invested basis', money(s.total_invested, currency)],
    ['Total profit / loss', money(s.total_pl, currency)],
    ['Annualized XIRR', s.xirr == null ? '—' : formatPercent(s.xirr)],
  ];
  if (detailed) metrics.splice(2, 0, ['Realized profit / loss', money(s.realized_pl, currency)],
    ['Unrealized profit / loss', money(s.unrealized_pl, currency)]);
  return <dl className="wp-metrics">{metrics.map(([k,v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
}

function Health({ health }) {
  return <section className="wp-panel wp-health"><header><h2>Portfolio checks</h2></header>
    {health.map(h => <div className={'wp-check wp-' + h.status} key={h.id}><b>{h.label}</b><p>{h.detail}</p></div>)}
  </section>;
}

export default function WealthPrototype(props) {
  const { summary, currency, scope, trend, health } = props;
  const [params, setParams] = useSearchParams();
  const variant = params.get('variant');
  const keys = Object.keys(variants);
  function change(step) {
    const next = new URLSearchParams(params);
    next.set('variant', keys[(keys.indexOf(variant) + step + keys.length) % keys.length]);
    setParams(next, { replace: true, preventScrollReset: true });
  }
  return <div className={'wp wp-' + variant} data-testid="wealth-prototype">
    <div className="wp-context"><span>{scope}</span><span>{currency}</span></div>
    <h1>{variant === 'A' ? 'Wealth overview' : variants[variant]}</h1>
    <div className="wp-value"><small>Current portfolio value</small><strong>{money(summary.current_value, currency)}</strong></div>
    {summary.nav_provisional && <p role="status">Portfolio value includes provisional NAVs.</p>}
    {variant === 'A' && <>
      <Measurements {...props} /><Trend trend={trend} />
      <div className="wp-split"><Mix {...props} /><Health health={health} /></div>
    </>}
    {variant === 'B' && <>
      <Mix key={scope} {...props} expanded /><Measurements {...props} />
      <details className="wp-fold"><summary>Performance history</summary><Trend trend={trend} /></details>
      <Health health={health} />
    </>}
    {variant === 'C' && <>
      <div className="wp-review"><section className="wp-panel"><header><h2>Return measures</h2><Link to="/compare">Compare <ArrowUpRight size={15} /></Link></header>
        <Measurements {...props} detailed /></section><Health health={health} /></div>
      <div className="wp-split"><Mix {...props} /><Trend trend={trend} /></div>
    </>}
    <nav className="wp-links" aria-label="Explore portfolio">{[['Holdings','/assets'],['Transactions','/transactions'],['Cash ledger','/cash'],['Fixed deposits','/fixed-deposits']].map(([name,path]) =>
      <Link key={path} to={path}>{name}<ArrowUpRight size={16} /></Link>)}</nav>
    <Switcher variant={variant} change={change} />
  </div>;
}
