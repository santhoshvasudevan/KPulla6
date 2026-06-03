import { describe, it, expect } from 'vitest';
import {
  monthlyHeatmapTone,
  monthlyHeatmapToneClass,
} from './metricSheetMonthlyHeatmap';

describe('monthlyHeatmapTone', () => {
  it('maps strong negative returns below -10%', () => {
    expect(monthlyHeatmapTone(-0.15)).toBe('strong-negative');
    expect(monthlyHeatmapTone(-0.1)).toBe('strong-negative');
  });

  it('maps soft negative returns between -10% and -3%', () => {
    expect(monthlyHeatmapTone(-0.05)).toBe('soft-negative');
    expect(monthlyHeatmapTone(-0.031)).toBe('soft-negative');
  });

  it('maps near-zero returns to neutral', () => {
    expect(monthlyHeatmapTone(0)).toBe('neutral');
    expect(monthlyHeatmapTone(0.02)).toBe('neutral');
    expect(monthlyHeatmapTone(-0.02)).toBe('neutral');
  });

  it('maps soft positive returns between +3% and +10%', () => {
    expect(monthlyHeatmapTone(0.05)).toBe('soft-positive');
    expect(monthlyHeatmapTone(0.099)).toBe('soft-positive');
  });

  it('maps strong positive returns at or above +10%', () => {
    expect(monthlyHeatmapTone(0.1)).toBe('strong-positive');
    expect(monthlyHeatmapTone(0.15)).toBe('strong-positive');
  });

  it('returns missing for null values', () => {
    expect(monthlyHeatmapTone(null)).toBe('missing');
  });
});

describe('monthlyHeatmapToneClass', () => {
  it('returns heatmap cell class names', () => {
    expect(monthlyHeatmapToneClass(0.12)).toBe(
      'metric-sheet-monthly-grid__cell--strong-positive'
    );
    expect(monthlyHeatmapToneClass(-0.12)).toBe(
      'metric-sheet-monthly-grid__cell--strong-negative'
    );
  });
});
