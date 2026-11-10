export default function MetricSheetNavCoverage({ coverage }) {
  if (!coverage) return null;

  const dates = coverage.start && coverage.end
    ? `${coverage.start} to ${coverage.end}`
    : 'No eligible observations';

  return (
    <span className="metric-sheet__coverage">
      {`Actual NAV coverage: ${dates}${coverage.incomplete ? ' (Incomplete)' : ''}`}
    </span>
  );
}
