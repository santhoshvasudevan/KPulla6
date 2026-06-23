import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ChartFrame from './ChartFrame';
import ChartLegend from './ChartLegend';
import ChartTooltipContent from './ChartTooltipContent';
import ChartRechartsTooltip from './ChartRechartsTooltip';
import { ChartEmptyState, ChartLoadingState, ChartErrorState } from './ChartStates';
import { buildLegendItems, getSeriesColorForRole, CHART_SERIES_ROLES } from './chartSeries';
import { getChartDensity, getChartHeight, getChartMinTickGap } from './chartDensity';
import {
  formatChartTooltipCurrency,
  formatChartTooltipPercent,
  formatChartTooltipValue,
} from './chartFormatters';
import { getChartCrosshairCursorProps } from './ChartCrosshair';
import { getChartAnimationProps } from './chartAnimation';

describe('chart density', () => {
  it('exposes sparse dashboard and denser analysis defaults', () => {
    expect(getChartHeight('dashboard')).toBe(380);
    expect(getChartHeight('analysis')).toBe(320);
    expect(getChartHeight('compact')).toBe(120);
    expect(getChartDensity('dashboard').axisDetail).toBe('sparse');
    expect(getChartDensity('analysis').axisDetail).toBe('detailed');
    expect(getChartMinTickGap('dashboard', true)).toBe(10);
  });
});

describe('chart series helpers', () => {
  it('resolves role-based colors without calculating values', () => {
    expect(getSeriesColorForRole(CHART_SERIES_ROLES.portfolio)).toBeTruthy();
    expect(getSeriesColorForRole(CHART_SERIES_ROLES.benchmark)).toBeTruthy();
    const items = buildLegendItems([
      { dataKey: 'portfolio', name: 'Portfolio', stroke: '#2563eb', role: 'portfolio' },
      { dataKey: 'benchmark', name: 'Benchmark', stroke: '#64748b', role: 'benchmark' },
    ]);
    expect(items).toHaveLength(2);
    expect(items[0].label).toBe('Portfolio');
    expect(items[1].role).toBe('benchmark');
  });
});

describe('chart formatters', () => {
  it('formats provided currency and percent values only', () => {
    expect(formatChartTooltipCurrency(1234.5, 'EUR')).toBe('€1,234.50');
    expect(formatChartTooltipPercent(0.1234, { showSign: true })).toBe('+12.34%');
    expect(formatChartTooltipValue(null, { kind: 'percent' })).toBe('—');
  });
});

describe('ChartFrame', () => {
  it('renders title, subtitle, and actions through ChartCard', () => {
    render(
      <ChartFrame
        title="Performance"
        subtitle="Portfolio value"
        toolbar={<button type="button">Export</button>}
      >
        <div>Chart canvas</div>
      </ChartFrame>
    );
    expect(screen.getByRole('heading', { name: 'Performance' })).toBeInTheDocument();
    expect(screen.getByText('Portfolio value')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument();
    expect(screen.getByText('Chart canvas')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    render(<ChartFrame title="Performance" loading loadingMessage="Loading performance…" />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading performance…');
  });

  it('renders empty state', () => {
    render(
      <ChartFrame
        title="Performance"
        empty
        emptyTitle="No performance data"
        emptyDescription="Try another range."
      />
    );
    expect(screen.getByText('No performance data')).toBeInTheDocument();
    expect(screen.getByText('Try another range.')).toBeInTheDocument();
  });

  it('renders error state', () => {
    render(<ChartFrame title="Performance" error="Request failed" errorTitle="Chart unavailable" />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Chart unavailable');
    expect(alert).toHaveTextContent('Request failed');
  });
});

describe('ChartTooltipContent', () => {
  it('renders date, values, benchmark, and backend-provided delta', () => {
    render(
      <ChartTooltipContent
        label="Jun 2026"
        items={[
          { key: 'portfolio', label: 'Portfolio', value: '€1,840,000.00', role: 'portfolio' },
          { key: 'benchmark', label: 'MSCI World', value: '+12.34%', role: 'benchmark' },
        ]}
        delta={{ label: 'Delta', value: '+2.10%' }}
      />
    );
    expect(screen.getByText('Jun 2026')).toBeInTheDocument();
    expect(screen.getByText('Portfolio')).toBeInTheDocument();
    expect(screen.getByText('€1,840,000.00')).toBeInTheDocument();
    expect(screen.getByText('MSCI World')).toBeInTheDocument();
    expect(screen.getByText('+12.34%')).toBeInTheDocument();
    expect(screen.getByText('Delta')).toBeInTheDocument();
    expect(screen.getByText('+2.10%')).toBeInTheDocument();
  });

  it('handles missing benchmark rows gracefully', () => {
    render(
      <ChartTooltipContent
        label="Jun 2026"
        items={[{ key: 'portfolio', label: 'Portfolio', value: '€100.00', role: 'portfolio' }]}
      />
    );
    expect(screen.queryByText('Benchmark')).not.toBeInTheDocument();
    expect(screen.getByText('€100.00')).toBeInTheDocument();
  });
});

describe('ChartRechartsTooltip', () => {
  it('formats active payload values without finance calculations', () => {
    render(
      <ChartRechartsTooltip
        active
        label="2026-06-01"
        payload={[
          { dataKey: 'portfolio', name: 'Portfolio', value: 0.05, color: '#2563eb' },
          { dataKey: 'benchmark', name: 'Benchmark', value: 0.03, color: '#64748b' },
        ]}
        valueKind="percent"
        benchmarkKeys={['benchmark']}
      />
    );
    expect(screen.getByText('2026-06-01')).toBeInTheDocument();
    expect(screen.getByText('Portfolio')).toBeInTheDocument();
    expect(screen.getByText('Benchmark')).toBeInTheDocument();
    expect(screen.getByText('+5.00%')).toBeInTheDocument();
    expect(screen.getByText('+3.00%')).toBeInTheDocument();
  });

  it('returns null when inactive or payload missing', () => {
    const { container, rerender } = render(
      <ChartRechartsTooltip active={false} payload={[{ value: 1 }]} />
    );
    expect(container).toBeEmptyDOMElement();
    rerender(<ChartRechartsTooltip active payload={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('ChartLegend', () => {
  it('renders legend items with accessible label', () => {
    render(
      <ChartLegend
        items={[
          { id: 'portfolio', label: 'Portfolio', color: '#2563eb', role: 'portfolio' },
          { id: 'benchmark', label: 'MSCI World', color: '#64748b', role: 'benchmark' },
        ]}
      />
    );
    expect(screen.getByLabelText('Chart legend')).toBeInTheDocument();
    expect(screen.getByText('Portfolio')).toBeInTheDocument();
    expect(screen.getByText('MSCI World')).toBeInTheDocument();
  });
});

describe('chart state primitives', () => {
  it('renders dedicated chart empty, loading, and error states', () => {
    const { rerender } = render(
      <ChartEmptyState title="No data" description="Sync prices to continue." />
    );
    expect(screen.getByText('No data')).toBeInTheDocument();

    rerender(<ChartLoadingState message="Loading chart…" />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading chart…');

    rerender(<ChartErrorState title="Failed" message="Network error" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Network error');
  });
});

describe('chart crosshair foundation', () => {
  it('exposes cursor props for Recharts tooltip crosshair', () => {
    expect(getChartCrosshairCursorProps('dashboard')).toMatchObject({ strokeWidth: 1 });
    expect(getChartCrosshairCursorProps('compact').strokeDasharray).toBe('4 4');
  });
});

describe('chart animation', () => {
  it('disables animation when inactive', () => {
    expect(getChartAnimationProps({ active: false })).toEqual({ isAnimationActive: false });
  });

  it('enables subtle animation when active', () => {
    expect(getChartAnimationProps({ active: true })).toMatchObject({
      isAnimationActive: true,
      animationDuration: 850,
      animationEasing: 'ease-out',
    });
  });
});
