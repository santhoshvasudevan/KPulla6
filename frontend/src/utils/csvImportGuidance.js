/** MF-11b — client-side CSV import guidance and sample file (no finance math). */

export const STOCK_CSV_COLUMNS =
  'Action, Date, ASSET SYMBOL, Qty, Price/Share, FEES (optional)';

export const MF_CSV_REQUIRED_COLUMNS =
  'Action, Scheme Code, Scheme Name, Folio Number, Investment Date, NAV Date, NAV, Units Allotted, Paid Value, Market Value';

export const MF_CSV_OPTIONAL_COLUMNS = 'Fees, Currency';

export const SAMPLE_MF_CSV_FILENAME = 'mutual-fund-transactions-sample.csv';

export function getSampleMutualFundCsvContent() {
  return (
    'Action,Scheme Code,Scheme Name,Folio Number,Investment Date,NAV Date,' +
    'NAV,Units Allotted,Paid Value,Market Value,Fees,Currency\n' +
    'BUY,120503,Sample Direct Growth Fund,FOLIO-12345,03/10/24,03/15/24,' +
    '42.50,100,4255.00,4250.00,5.00,INR\n'
  );
}

export function downloadSampleMutualFundCsv() {
  const blob = new Blob([getSampleMutualFundCsvContent()], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = SAMPLE_MF_CSV_FILENAME;
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
