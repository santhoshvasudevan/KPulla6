import { describe, it, expect } from 'vitest';
import sampleCompareMetricSheetPayload from '../components/metricSheet/fixtures/sampleCompareMetricSheetPayload';
import {
  compareBenchmarkLabel,
  compareChartLegendItems,
  compareOptionLabel,
  compareSubjectSummaryKpis,
} from './compareDisplay';

describe('compareDisplay', () => {
  const assetOptions = [
    { symbol: 'AAPL', label: 'AAPL', active: true },
    { symbol: 'MSFT', label: 'MSFT', active: true },
  ];

  it('resolves asset and benchmark labels from options', () => {
    expect(compareOptionLabel(assetOptions, 'AAPL')).toBe('AAPL');
    expect(
      compareBenchmarkLabel([{ symbol: '^GSPC', name: 'S&P 500' }], '^GSPC')
    ).toBe('S&P 500');
  });

  it('builds chart legend items from backend series order', () => {
    const items = compareChartLegendItems(
      sampleCompareMetricSheetPayload.subjects,
      sampleCompareMetricSheetPayload.normalized_series
    );
    expect(items).toHaveLength(2);
    expect(items[0].label).toBe('Apple Inc.');
    expect(items[0].color).toBeTruthy();
  });

  it('extracts subject KPI values without calculation', () => {
    const kpis = compareSubjectSummaryKpis(sampleCompareMetricSheetPayload.subjects);
    expect(kpis[0].cumulativeReturn).toBe(0.1234);
    expect(kpis[1].cumulativeReturn).toBe(0.0567);
  });
});
