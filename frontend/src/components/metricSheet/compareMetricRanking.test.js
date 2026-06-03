import { describe, it, expect } from 'vitest';
import {
  COMPARE_HIGHLIGHT,
  getCompareHighlightStates,
  getMetricCompareDirection,
} from './compareMetricRanking';

describe('getMetricCompareDirection', () => {
  it('marks higher-is-better metrics', () => {
    expect(getMetricCompareDirection('cagr')).toBe('higher');
    expect(getMetricCompareDirection('sharpe_ratio')).toBe('higher');
  });

  it('marks lower-is-better metrics', () => {
    expect(getMetricCompareDirection('volatility_annualized')).toBe('lower');
  });

  it('marks max_drawdown as less_negative', () => {
    expect(getMetricCompareDirection('max_drawdown')).toBe('less_negative');
  });

  it('marks beta, correlation, and tracking_error as neutral', () => {
    expect(getMetricCompareDirection('beta')).toBe('neutral');
    expect(getMetricCompareDirection('correlation')).toBe('neutral');
    expect(getMetricCompareDirection('tracking_error')).toBe('neutral');
  });
});

describe('getCompareHighlightStates', () => {
  it('highlights higher cumulative return as better', () => {
    expect(getCompareHighlightStates('cumulative_return', [0.12, 0.05])).toEqual([
      COMPARE_HIGHLIGHT.BETTER,
      COMPARE_HIGHLIGHT.WORSE,
    ]);
  });

  it('highlights lower volatility as better', () => {
    expect(getCompareHighlightStates('volatility_annualized', [0.2, 0.18])).toEqual([
      COMPARE_HIGHLIGHT.WORSE,
      COMPARE_HIGHLIGHT.BETTER,
    ]);
  });

  it('treats less negative max_drawdown as better', () => {
    expect(getCompareHighlightStates('max_drawdown', [-0.25, -0.1])).toEqual([
      COMPARE_HIGHLIGHT.WORSE,
      COMPARE_HIGHLIGHT.BETTER,
    ]);
    expect(getCompareHighlightStates('max_drawdown', [-0.08, -0.06])).toEqual([
      COMPARE_HIGHLIGHT.WORSE,
      COMPARE_HIGHLIGHT.BETTER,
    ]);
  });

  it('returns neutral for beta and correlation', () => {
    expect(getCompareHighlightStates('beta', [1.05, 0.95])).toEqual([
      COMPARE_HIGHLIGHT.NEUTRAL,
      COMPARE_HIGHLIGHT.NEUTRAL,
    ]);
    expect(getCompareHighlightStates('correlation', [0.88, 0.82])).toEqual([
      COMPARE_HIGHLIGHT.NEUTRAL,
      COMPARE_HIGHLIGHT.NEUTRAL,
    ]);
  });

  it('returns neutral when either value is null', () => {
    expect(getCompareHighlightStates('cagr', [0.12, null])).toEqual([
      COMPARE_HIGHLIGHT.NEUTRAL,
      COMPARE_HIGHLIGHT.NEUTRAL,
    ]);
    expect(getCompareHighlightStates('xirr', [null, null])).toEqual([
      COMPARE_HIGHLIGHT.NEUTRAL,
      COMPARE_HIGHLIGHT.NEUTRAL,
    ]);
  });

  it('returns tie for equal values within tolerance', () => {
    expect(getCompareHighlightStates('sharpe_ratio', [1.1, 1.1])).toEqual([
      COMPARE_HIGHLIGHT.TIE,
      COMPARE_HIGHLIGHT.TIE,
    ]);
  });

  it('returns unknown for invalid value arrays', () => {
    expect(getCompareHighlightStates('cagr', [0.1])).toEqual([
      COMPARE_HIGHLIGHT.UNKNOWN,
      COMPARE_HIGHLIGHT.UNKNOWN,
    ]);
  });
});
