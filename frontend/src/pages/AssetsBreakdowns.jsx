import { AppTable, AppTableCell, AppTableHeaderCell, DataTableShell, EmptyState, WarningBanner } from '../components/ui';
import { formatCurrency, formatPercent } from '../utils/formatters';

const units = new Intl.NumberFormat(undefined, { maximumFractionDigits: 8 });

function valueLabel(value, currency) {
  return value == null ? '—' : formatCurrency(value, currency);
}

function weightLabel(weight) {
  return weight == null ? '—' : formatPercent(weight);
}

function CategoryNode({ node, currency }) {
  const metrics = (
    <span className="assets-breakdowns__metrics">
      <span>{valueLabel(node.value, currency)}</span>
      <span>{weightLabel(node.weight)}</span>
      <span>{node.scheme_count} {node.scheme_count === 1 ? 'scheme' : 'schemes'}</span>
      {node.units != null && <span>{units.format(node.units)} units</span>}
    </span>
  );
  if (!node.children) {
    return <div className="assets-breakdowns__category-row"><span>{node.name}</span>{metrics}</div>;
  }
  return (
    <details>
      <summary><span className="assets-breakdowns__category-name">{node.name}</span>{metrics}</summary>
      <div className="assets-breakdowns__children">
        {node.children.map((child) => <CategoryNode key={child.id} node={child} currency={currency} />)}
      </div>
    </details>
  );
}

export default function AssetsBreakdowns({ report, currency }) {
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
        <p>Market value · % of visible mutual fund value · distinct schemes · units at scheme level</p>
        {report.categories.map((node) => <CategoryNode key={node.id} node={node} currency={currency} />)}
      </div>
    </section>
  );
}
