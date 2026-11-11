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
  const [category, setCategory] = useState('');
  const [subcategory, setSubcategory] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function open() {
    const [initialCategory = '', initialSubcategory = ''] = node.personal_category || node.provider_category || [];
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
      await fundCategoryRequest(node.scheme_code, method, method === 'PUT' ? { category, subcategory } : undefined);
      setEditing(false);
      onChanged();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  if (!editing) return <button type="button" onClick={open}>Edit category</button>;
  return (
    <form className="assets-category-editor" onSubmit={(event) => { event.preventDefault(); save('PUT'); }}>
      <p>Provider: {node.provider_category?.filter(Boolean).join(' → ') || 'Not recorded'}</p>
      <label>Category <input value={category} onChange={(event) => setCategory(event.target.value)}
        required maxLength={100} list={`${listId}-categories`} /></label>
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

function CategoryNode({ node, currency, depth = 0, onChanged }) {
  const name = node.name;
  const row = (
    <>
      <span className="assets-breakdowns__category-name" style={{ '--category-depth': depth }}>
        {node.children && <span className="assets-breakdowns__disclosure" aria-hidden="true">▸</span>}
        {name}
        {node.personal_category && <small>Personal category</small>}
        {node.category_missing && <small>Category not recorded</small>}
      </span>
      <span>{valueLabel(node.value, currency)}</span>
      <span>{weightLabel(node.weight)}</span>
      <span>{node.scheme_count}</span>
      <span>{node.units == null ? '—' : units.format(node.units)}</span>
    </>
  );
  if (!node.children) {
    return (
      <div>
        <div className="assets-breakdowns__category-row">{row}</div>
        {node.scheme_code && <CategoryEditor node={node} onChanged={onChanged} />}
      </div>
    );
  }
  return (
    <details open={depth === 0 || undefined}>
      <summary className="assets-breakdowns__category-row">{row}</summary>
      {node.children.map((child) => <CategoryNode key={child.id} node={child} currency={currency} depth={depth + 1} onChanged={onChanged} />)}
    </details>
  );
}

export default function AssetsBreakdowns({ report, currency, onChanged }) {
  if (!report?.scheme_count) return <EmptyState title="No mutual funds in this view." />;
  return (
    <section id="assets-breakdowns" className="assets-breakdowns" aria-label="Mutual fund breakdowns">
      <p>
        {report.scheme_count} distinct {report.scheme_count === 1 ? 'scheme' : 'schemes'} ·{' '}
        {report.folio_count} distinct {report.folio_count === 1 ? 'folio' : 'folios'} ·{' '}
        {valueLabel(report.total, currency)} visible mutual fund value
      </p>
      {report.incomplete && <WarningBanner severity="warning" message="Some fund values are unavailable. Percentages are unavailable until the visible fund total is complete." />}
      <DataTableShell title="By AMC" dense>
        <AppTable compact>
          <thead><tr>
            <AppTableHeaderCell>AMC</AppTableHeaderCell>
            <AppTableHeaderCell numeric>Market value</AppTableHeaderCell>
            <AppTableHeaderCell numeric>% of visible mutual fund value</AppTableHeaderCell>
            <AppTableHeaderCell numeric>Distinct schemes</AppTableHeaderCell>
            <AppTableHeaderCell numeric>Distinct folios</AppTableHeaderCell>
          </tr></thead>
          <tbody>{report.amc.map((row) => (
            <tr key={row.name}>
              <AppTableCell>{row.name}</AppTableCell>
              <AppTableCell numeric>{valueLabel(row.value, currency)}</AppTableCell>
              <AppTableCell numeric>{weightLabel(row.weight)}</AppTableCell>
              <AppTableCell numeric>{row.scheme_count}</AppTableCell>
              <AppTableCell numeric>{row.folio_count}</AppTableCell>
            </tr>
          ))}</tbody>
        </AppTable>
      </DataTableShell>
      <div>
        <h3>By fund category</h3>
        <p>Expand a classification, category, or subcategory to see its schemes. Shares use visible mutual fund value.</p>
        {report.missing_category_count > 0 && <p>
          Category metadata is missing for {report.missing_category_count} {report.missing_category_count === 1 ? 'scheme' : 'schemes'} in this view.
        </p>}
        <div className="assets-breakdowns__category-scroll">
          <div className="assets-breakdowns__category-grid">
            <div className="assets-breakdowns__category-row assets-breakdowns__category-header">
              <span>Classification / category / scheme</span><span>Market value</span>
              <span>Share</span><span>Schemes</span><span>Units</span>
            </div>
            {report.categories.map((node) => <CategoryNode key={node.id} node={node} currency={currency} onChanged={onChanged} />)}
          </div>
        </div>
      </div>
    </section>
  );
}
