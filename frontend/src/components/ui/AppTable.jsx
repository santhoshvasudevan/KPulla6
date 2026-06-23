export function AppTableHeaderCell({ children, numeric = false, className = '', ...props }) {
  const classes = ['ui-app-table__cell', numeric ? 'ui-app-table__cell--numeric' : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <th className={classes} scope="col" {...props}>
      {children}
    </th>
  );
}

export function AppTableCell({ children, numeric = false, className = '', ...props }) {
  const classes = ['ui-app-table__cell', numeric ? 'ui-app-table__cell--numeric' : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <td className={classes} {...props}>
      {children}
    </td>
  );
}

export default function AppTable({ children, compact = false, className = '', ...props }) {
  const classes = ['ui-app-table', compact ? 'ui-app-table--compact' : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <table className={classes} {...props}>
      {children}
    </table>
  );
}
