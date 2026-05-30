/** Display-only helpers: organize backend monthly/yearly return rows into a grid. */

export const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

export const MONTH_NAMES_FULL = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

/**
 * Map backend `periodic_returns.monthly` / `.yearly` into year rows for the grid.
 * Does not compute returns — only parses period keys and copies backend values.
 */
export function buildMonthlyReturnsGrid(monthly = [], yearly = []) {
  const monthlyByPeriod = new Map();
  for (const row of monthly) {
    if (row?.period) {
      monthlyByPeriod.set(row.period, row.return);
    }
  }

  const yearlyByYear = new Map();
  for (const row of yearly) {
    if (row?.period) {
      yearlyByYear.set(String(row.period), row.return);
    }
  }

  const years = new Set();
  for (const period of monthlyByPeriod.keys()) {
    const year = String(period).slice(0, 4);
    if (/^\d{4}$/.test(year)) years.add(year);
  }
  for (const year of yearlyByYear.keys()) {
    if (/^\d{4}$/.test(year)) years.add(year);
  }

  const sortedYears = [...years].sort();

  return sortedYears.map((year) => ({
    year,
    months: MONTH_LABELS.map((label, index) => {
      const monthNum = String(index + 1).padStart(2, '0');
      const period = `${year}-${monthNum}`;
      return {
        label,
        monthIndex: index,
        period,
        return: monthlyByPeriod.has(period) ? monthlyByPeriod.get(period) : null,
      };
    }),
    yearlyReturn: yearlyByYear.has(year) ? yearlyByYear.get(year) : null,
  }));
}

export function monthlyCellAriaLabel({ monthIndex, year, formattedValue, hasValue }) {
  const monthName = MONTH_NAMES_FULL[monthIndex] ?? 'Month';
  if (!hasValue) {
    return `${monthName} ${year} return not available`;
  }
  return `${monthName} ${year} return ${formattedValue}`;
}
