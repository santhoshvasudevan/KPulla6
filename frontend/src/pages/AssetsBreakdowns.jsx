import { useId, useState } from "react";
import { fundCategoryRequest } from "../api";
import { AppTable, AppTableCell, AppTableHeaderCell, DataTableShell, EmptyState, WarningBanner } from '../components/ui';
import { formatCurrency, formatPercent } from '../utils/formatters';

const units = new Intl.NumberFormat(undefined, { maximumFractionDigits: 8 });

function valueLabel(value, currency) {
  return value == null ? '—' : formatCurrency(value, currency);
}

function weightLabel(weight) {
  return weight == null ? '—' : formatPercent(weight);
}

function CategoryEditor({ node, onChanged }) {
  const listId = useId();
  const [editing, setEditing] = useState(false);
  const [labels, setLabels] = useState([]);
  const [classification, setClassification] = useState('');
  const [category, setCategory] = useState('');
  const [subcategory, setSubcategory] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function open() {
    const [initialClass = '', initialCategory = '', initialSubcategory = ''] = node.effective_taxonomy || [];
    setClassification(initialClass === 'Needs classification' ? '' : initialClass);
    setCategory(initialCategory);
    setSubcategory(initialSubcategory);
    setEditing(true);
    setError('');
    try {
      setLabels((await fundCategoryRequest(node.scheme_code)).labels);
    } catch (failure) {
      setError(failure.message);
    }
  }

  async function save(method) {
    setBusy(true);
    setError('');
    try {
      await fundCategoryRequest(node.scheme_code, method, method === 'PUT' ? { classification, category, subcategory } : undefined);
      setEditing(false);
      onChanged();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  if (!editing) return <button type="button" onClick={open}>Edit classification and category</button>;
  return (
    <form className="assets-category-editor" onSubmit={(event) => { event.preventDefault(); save('PUT'); }}>
      <p>Provider: {node.provider_category?.filter(Boolean).join(' → ') || 'Not recorded'}</p>
      <label>Classification <select required value={classification} onChange={(event) => setClassification(event.target.value)}>
        <option value="">Select classification</option>
        {['Equity', 'Debt', 'Hybrid'].map((label) => <option key={label}>{label}</option>)}
      </select></label>
      <label>Category <input value={category} onChange={(event) => setCategory(event.target.value)}
        maxLength={100} list={`${listId}-categories`} /></label>
      <label>Subcategory <input value={subcategory} onChange={(event) => setSubcategory(event.target.value)}
        maxLength={100} list={`${listId}-subcategories`} /></label>
      <datalist id={`${listId}-categories`}>{[...new Set(labels.map((label) => label.category))]
        .map((label) => <option key={label} value={label} />)}</datalist>
      <datalist id={`${listId}-subcategories`}>{[...new Set(labels.filter((label) => label.category === category)
        .map((label) => label.subcategory).filter(Boolean))]
        .map((label) => <option key={label} value={label} />)}</datalist>
      <button type="submit" disabled={busy}>Save category</button>
      {node.personal_category && <button type="button" disabled={busy} onClick={() => save('DELETE')}>Reset to provider</button>}
      <button type="button" disabled={busy} onClick={() => setEditing(false)}>Cancel</button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}

function CategoryNode({ node, currency, depth = 0, onChanged, order, folioView }) {
  const name = node.name;
  const row = (
    <>
      <span className="assets-breakdowns__category-name" style={{ '--category-depth': depth }}>
        {node.children && <span className="assets-breakdowns__disclosure" aria-hidden="true">▸</span>}
        {name}
        {node.fund_house && <small>{node.fund_house}</small>}
        {folioView && node.portfolio_names?.length > 0 && <small>{node.portfolio_names.join(" · ")}</small>}
        {node.personal_category && <small>Personal category</small>}
        {node.category_missing && <small>Category not recorded</small>}
      </span>
      <span>{valueLabel(node.value, currency)}</span>
      <span>{weightLabel(node.weight)}</span>
      <span>{node.scheme_count}</span>
      <span>{node.units == null ? '—' : units.format(node.units)}</span>
      <span>{!node.children && node.scheme_code && <CategoryEditor node={node} onChanged={onChanged} />}</span>
    </>
  );
  if (!node.children) {
    return (
      <div>
        <div className="assets-breakdowns__category-row">{row}</div>

      </div>
    );
  }
  return (
    <details open={depth === 0 && !folioView || undefined}>
      <summary className="assets-breakdowns__category-row">{row}</summary>
      {sortRows(node.children, order).map((child) => <CategoryNode key={child.id} node={child} currency={currency} depth={depth + 1} onChanged={onChanged} order={order} folioView={folioView} />)}
    </details>
  );
}

function sortRows(rows, { field, direction }) {
  return [...rows].sort((a, b) => {
    const left = a[field], right = b[field];
    if (left == null && right != null) return 1;
    if (left != null && right == null) return -1;
    return ((left ?? 0) - (right ?? 0)) * direction || a.name.localeCompare(b.name);
  });
}

export default function AssetsBreakdowns({ report, currency, onChanged }) {
  const [view, setView] = useState('classification');
  const [order, setOrder] = useState({ field: 'value', direction: -1 });
  const sortButton = (field, label) => (
    <button type="button" onClick={() => setOrder((previous) => ({
      field, direction: previous.field === field ? -previous.direction : -1,
    }))}>{label}{order.field === field ? (order.direction === -1 ? ' ↓' : ' ↑') : ''}</button>
  );
  if (!report?.scheme_count) return <EmptyState title="No mutual funds in this view." />;
  return (
    <section id="assets-breakdowns" className="assets-breakdowns" aria-label="Mutual fund breakdowns">
      <p>
        {report.scheme_count} distinct {report.scheme_count === 1 ? 'scheme' : 'schemes'} ·{' '}
        {report.folio_count} distinct {report.folio_count === 1 ? 'folio' : 'folios'} ·{' '}
        {valueLabel(report.total, currency)} visible mutual fund value
      </p>
      {report.incomplete && <WarningBanner severity="warning" message="Some fund values are unavailable. Percentages are unavailable until the visible fund total is complete." />}
      <div className="assets-section-nav" role="group" aria-label="Breakdown views">
        {[['amc', 'By AMC'], ['classification', 'By classification'], ['folio', 'By folio']].map(([key, label]) => (
          <button key={key} type="button" aria-pressed={view === key} onClick={() => setView(key)}>{label}</button>
        ))}
      </div>
      {view === 'amc' ? <DataTableShell title="By AMC" dense>
        <AppTable compact>
          <thead><tr>
            <AppTableHeaderCell>AMC</AppTableHeaderCell>
            <AppTableHeaderCell numeric>{sortButton("value", "Market value")}</AppTableHeaderCell>
            <AppTableHeaderCell numeric>{sortButton("weight", "% of visible mutual fund value")}</AppTableHeaderCell>
            <AppTableHeaderCell numeric>Distinct schemes</AppTableHeaderCell>
            <AppTableHeaderCell numeric>Distinct folios</AppTableHeaderCell>
          </tr></thead>
          <tbody>{sortRows(report.amc, order).map((row) => (
            <tr key={row.name}>
              <AppTableCell>{row.name}</AppTableCell>
              <AppTableCell numeric>{valueLabel(row.value, currency)}</AppTableCell>
              <AppTableCell numeric>{weightLabel(row.weight)}</AppTableCell>
              <AppTableCell numeric>{row.scheme_count}</AppTableCell>
              <AppTableCell numeric>{row.folio_count}</AppTableCell>
            </tr>
          ))}</tbody>
        </AppTable>
      </DataTableShell> : <div>
        <h3>{view === "folio" ? "By folio" : "By classification"}</h3>
        <p>Expand a classification, category, or subcategory to see its schemes. Shares use visible mutual fund value.</p>
        {report.missing_category_count > 0 && <p>
          Category metadata is missing for {report.missing_category_count} {report.missing_category_count === 1 ? 'scheme' : 'schemes'} in this view.
        </p>}
        <div className="assets-breakdowns__category-scroll">
          <div className="assets-breakdowns__category-grid">
            <div className="assets-breakdowns__category-row assets-breakdowns__category-header">
              <span>{view === "folio" ? "Folio / fund house / scheme" : "Classification / category / scheme"}</span>
              <span>{sortButton("value", "Market value")}</span>
              <span>{sortButton("weight", "Share")}</span><span>Schemes</span><span>Units</span><span>Actions</span>
            </div>
            {sortRows(view === "folio" ? report.folios || [] : report.categories, order).map((node) => <CategoryNode key={node.id} node={node} currency={currency} onChanged={onChanged} order={order} folioView={view === "folio"} />)}
          </div>
        </div>
      </div>}
    </section>
  );
}
