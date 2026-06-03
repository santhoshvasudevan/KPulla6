import { useMemo } from 'react';
import {
  formatMetricPercentFraction,
  METRIC_EM_DASH,
} from '../../utils/metricFormatters';
import {
  buildMonthlyReturnsGrid,
  MONTH_LABELS,
  monthlyCellAriaLabel,
} from './metricSheetMonthlyGrid';
import { monthlyHeatmapToneClass } from './metricSheetMonthlyHeatmap';
import './metricSheet.css';

function toneClass(value) {
  return monthlyHeatmapToneClass(value);
}

function MonthlyGridCell({ monthIndex, year, value }) {
  const hasValue = value != null && value !== '' && !Number.isNaN(Number(value));
  const formatted = hasValue
    ? formatMetricPercentFraction(value, { showSign: true })
    : METRIC_EM_DASH;

  return (
    <td
      className={['metric-sheet-monthly-grid__cell', toneClass(value)].join(' ')}
      aria-label={monthlyCellAriaLabel({
        monthIndex,
        year,
        formattedValue: formatted,
        hasValue,
      })}
    >
      <span className="metric-sheet-monthly-grid__cell-value">{formatted}</span>
    </td>
  );
}

/**
 * Monthly returns heatmap/grid from backend `periodic_returns.monthly` (+ optional yearly column).
 */
export default function MetricSheetMonthlyReturnsGrid({
  monthly = [],
  yearly = [],
  className = '',
}) {
  const rows = useMemo(() => buildMonthlyReturnsGrid(monthly, yearly), [monthly, yearly]);
  const showYearlyColumn = (yearly ?? []).length > 0;

  if (!monthly?.length) {
    return (
      <p className="metric-sheet__empty-inline">
        No monthly return data available for this range.
      </p>
    );
  }

  return (
    <div
      className={[
        'metric-sheet-table-scroll',
        'metric-sheet-monthly-grid-scroll',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <table className="metric-sheet-monthly-grid metric-sheet__data-table">
        <caption className="metric-sheet-monthly-grid__caption">Monthly returns</caption>
        <thead>
          <tr>
            <th scope="col" className="metric-sheet-monthly-grid__year-col">
              Year
            </th>
            {MONTH_LABELS.map((label) => (
              <th key={label} scope="col" className="metric-sheet-monthly-grid__month-col">
                {label}
              </th>
            ))}
            {showYearlyColumn ? (
              <th scope="col" className="metric-sheet-monthly-grid__year-total-col">
                Year Return
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.year}>
              <th scope="row" className="metric-sheet-monthly-grid__year-col">
                {row.year}
              </th>
              {row.months.map((cell) => (
                <MonthlyGridCell
                  key={cell.period}
                  monthIndex={cell.monthIndex}
                  year={row.year}
                  value={cell.return}
                />
              ))}
              {showYearlyColumn ? (
                <td
                  className={[
                    'metric-sheet-monthly-grid__cell',
                    'metric-sheet-monthly-grid__year-total-col',
                    toneClass(row.yearlyReturn),
                  ].join(' ')}
                  aria-label={
                    row.yearlyReturn != null && row.yearlyReturn !== ''
                      ? `${row.year} full-year return ${formatMetricPercentFraction(row.yearlyReturn, { showSign: true })}`
                      : `${row.year} full-year return not available`
                  }
                >
                  <span className="metric-sheet-monthly-grid__cell-value">
                    {row.yearlyReturn != null && row.yearlyReturn !== ''
                      ? formatMetricPercentFraction(row.yearlyReturn, { showSign: true })
                      : METRIC_EM_DASH}
                  </span>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
