import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import {
  Button,
  PageHeader,
  SectionHeader,
  AppCard,
  MetricCard,
  KpiCard,
  SectionCard,
  StatusBadge,
  AssetClassPill,
  TrendBadge,
  WarningBanner,
  EmptyState,
  LoadingState,
  ErrorState,
  CurrencyValue,
  PercentValue,
  ChartCard,
  DataTableShell,
  AppTable,
  AppTableCell,
  AppTableHeaderCell,
  SegmentedControl,
} from './index';

describe('Button', () => {
  it('renders children and handles click', () => {
    const onClick = vi.fn();
    render(
      <Button variant="primary" onClick={onClick}>
        Save
      </Button>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('supports disabled state', () => {
    render(
      <Button variant="secondary" disabled>
        Disabled
      </Button>
    );
    expect(screen.getByRole('button', { name: 'Disabled' })).toBeDisabled();
  });
});

describe('PageHeader', () => {
  it('renders title, subtitle, eyebrow, and actions', () => {
    render(
      <PageHeader
        eyebrow="Portfolio"
        title="Dashboard"
        subtitle="Overview"
        breadcrumb={<span>Home / Dashboard</span>}
        actions={<button type="button">Export</button>}
      />
    );
    expect(screen.getByText('Portfolio')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByLabelText('Breadcrumb')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument();
  });
});

describe('MetricCard', () => {
  it('renders label and value with tone class', () => {
    const { container } = render(
      <MetricCard label="Total P/L" value="€1,234.56" tone="positive" helperText="All time" />
    );
    expect(screen.getByText('Total P/L')).toBeInTheDocument();
    expect(screen.getByText('€1,234.56')).toBeInTheDocument();
    expect(screen.getByText('All time')).toBeInTheDocument();
    expect(container.querySelector('.ui-metric-card--positive')).toBeInTheDocument();
  });

  it('uses fluid typography for large INR hero values without wrapping', () => {
    const { container } = render(
      <MetricCard
        size="hero"
        label="Current Value"
        value={<CurrencyValue value={16650000} currency="INR" />}
      />
    );
    const valueEl = screen.getByTitle('₹16,650,000.00');
    expect(valueEl.textContent).toBe('₹16,650,000.00');
    expect(valueEl.closest('.ui-metric-card__value')).toBeInTheDocument();
    expect(container.querySelector('.ui-metric-card--hero')).toBeInTheDocument();
  });
});

describe('Executive OS card primitives', () => {
  it('renders a reusable section header with title, subtitle, and actions', () => {
    render(
      <SectionHeader
        eyebrow="Portfolio"
        title="Operating View"
        subtitle="Tables and diagnostics"
        actions={<button type="button">Refresh</button>}
      />
    );
    expect(screen.getByText('Portfolio')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Operating View' })).toBeInTheDocument();
    expect(screen.getByText('Tables and diagnostics')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument();
  });

  it('renders AppCard header, body, actions, and footer', () => {
    render(
      <AppCard
        title="Portfolio Health"
        subtitle="X-ray style review"
        actions={<button type="button">View all</button>}
        footer={<span>Cached data only</span>}
      >
        <p>NAV freshness</p>
      </AppCard>
    );
    expect(screen.getByRole('heading', { name: 'Portfolio Health' })).toBeInTheDocument();
    expect(screen.getByText('X-ray style review')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'View all' })).toBeInTheDocument();
    expect(screen.getByText('NAV freshness')).toBeInTheDocument();
    expect(screen.getByText('Cached data only')).toBeInTheDocument();
  });

  it('keeps KpiCard compatible with MetricCard props', () => {
    const { container } = render(<KpiCard label="Total P/L" value="+12.5%" variant="gain" />);
    expect(screen.getByText('Total P/L')).toBeInTheDocument();
    expect(screen.getByText('+12.5%')).toBeInTheDocument();
    expect(container.querySelector('.ui-metric-card--positive')).toBeInTheDocument();
  });
});

describe('SectionCard', () => {
  it('renders title and children', () => {
    render(
      <SectionCard title="Display & tax" subtitle="App preferences">
        <p>Form content</p>
      </SectionCard>
    );
    expect(screen.getByText('Display & tax')).toBeInTheDocument();
    expect(screen.getByText('App preferences')).toBeInTheDocument();
    expect(screen.getByText('Form content')).toBeInTheDocument();
  });
});

describe('StatusBadge', () => {
  it('renders default label for known status', () => {
    render(<StatusBadge status="price_missing" />);
    expect(screen.getByText('Price missing')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders custom label', () => {
    render(<StatusBadge status="neutral" label="Custom" />);
    expect(screen.getByText('Custom')).toBeInTheDocument();
  });

  it('supports semantic variants with accessible labels', () => {
    render(
      <>
        <StatusBadge status="success" label="Current" />
        <StatusBadge status="danger" label="Action needed" />
        <StatusBadge status="info" label="Benchmark ready" />
      </>
    );
    expect(screen.getByRole('status', { name: 'Current' })).toHaveTextContent('Current');
    expect(screen.getByRole('status', { name: 'Action needed' })).toHaveTextContent('Action needed');
    expect(screen.getByRole('status', { name: 'Benchmark ready' })).toHaveTextContent('Benchmark ready');
  });
});

describe('Badge and pill primitives', () => {
  it('renders asset class variant labels', () => {
    render(
      <>
        <AssetClassPill variant="stock" />
        <AssetClassPill variant="mutualFund" />
        <AssetClassPill variant="fixedDeposit" />
        <AssetClassPill variant="cash" />
        <AssetClassPill variant="benchmark" />
      </>
    );
    expect(screen.getByLabelText('Asset class: Stock')).toHaveTextContent('Stock');
    expect(screen.getByLabelText('Asset class: Mutual Fund')).toHaveTextContent('Mutual Fund');
    expect(screen.getByLabelText('Asset class: Fixed Deposit')).toHaveTextContent('Fixed Deposit');
    expect(screen.getByLabelText('Asset class: Cash')).toHaveTextContent('Cash');
    expect(screen.getByLabelText('Asset class: Benchmark')).toHaveTextContent('Benchmark');
  });

  it('renders trend badge variants with text and accessible labels', () => {
    render(
      <>
        <TrendBadge variant="gain" value="+4.2%" />
        <TrendBadge variant="loss" value="-1.1%" />
      </>
    );
    expect(screen.getByLabelText('Gain: +4.2%')).toHaveTextContent('+4.2%');
    expect(screen.getByLabelText('Loss: -1.1%')).toHaveTextContent('-1.1%');
  });
});

describe('WarningBanner', () => {
  it('uses alert role for error severity', () => {
    render(<WarningBanner severity="error" title="Save failed" message="Invalid tax rate" />);
    const banner = screen.getByRole('alert');
    expect(banner).toHaveTextContent('Save failed');
    expect(banner).toHaveTextContent('Invalid tax rate');
  });

  it('uses status role for success severity', () => {
    render(<WarningBanner severity="success" message="Settings saved." />);
    expect(screen.getByRole('status')).toHaveTextContent('Settings saved.');
  });
});

describe('EmptyState', () => {
  it('renders title, description, and action', () => {
    render(
      <EmptyState
        title="No holdings"
        description="Add transactions to see assets."
        action={<button type="button">Add transaction</button>}
      />
    );
    expect(screen.getByText('No holdings')).toBeInTheDocument();
    expect(screen.getByText('Add transactions to see assets.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add transaction' })).toBeInTheDocument();
  });
});

describe('LoadingState', () => {
  it('exposes loading status to assistive tech', () => {
    render(<LoadingState message="Loading settings…" />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading settings…');
  });
});

describe('ErrorState', () => {
  it('renders title and message with alert role', () => {
    render(<ErrorState title="Error loading settings" message="Network failed" />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Error loading settings');
    expect(alert).toHaveTextContent('Network failed');
  });

  it('renders retry button when onRetry provided', () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Failed" onRetry={onRetry} />);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe('CurrencyValue', () => {
  it('formats currency using formatter utility', () => {
    render(<CurrencyValue value={1234.5} currency="EUR" />);
    expect(screen.getByText('€1,234.50')).toBeInTheDocument();
  });

  it('shows fallback for null value', () => {
    render(<CurrencyValue value={null} fallback="—" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('applies positive tone class and sign', () => {
    const { container } = render(<CurrencyValue value={100} currency="USD" tone="positive" showSign />);
    expect(container.querySelector('.ui-currency-value--positive')).toBeInTheDocument();
    expect(container.textContent).toBe('+$100.00');
  });

  it('exposes full formatted value in title for large amounts', () => {
    render(<CurrencyValue value={9876543.21} currency="INR" />);
    expect(screen.getByTitle('₹9,876,543.21')).toBeInTheDocument();
  });
});

describe('PercentValue', () => {
  it('formats decimal fraction as percent', () => {
    render(<PercentValue value={0.125} />);
    expect(screen.getByText('12.50%')).toBeInTheDocument();
  });

  it('shows fallback for null value', () => {
    render(<PercentValue value={null} />);
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });
});

describe('ChartCard', () => {
  it('renders title, toolbar, body, and footer', () => {
    render(
      <ChartCard
        title="Value History"
        subtitle="Last 12 months"
        status={<StatusBadge status="info" label="Cached" />}
        legend={<AssetClassPill variant="benchmark" />}
        toolbar={<button type="button">Export</button>}
        footer={<span>Chart footer</span>}
      >
        <div>Chart body</div>
      </ChartCard>
    );
    expect(screen.getByRole('heading', { name: 'Value History' })).toBeInTheDocument();
    expect(screen.getByText('Last 12 months')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Cached' })).toBeInTheDocument();
    expect(screen.getByLabelText('Asset class: Benchmark')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument();
    expect(screen.getByText('Chart body')).toBeInTheDocument();
    expect(screen.getByText('Chart footer')).toBeInTheDocument();
  });
});

describe('DataTable primitives', () => {
  it('renders title, subtitle, actions, and numeric cells', () => {
    const { container } = render(
      <DataTableShell
        title="Holdings"
        subtitle="Active positions"
        actions={<button type="button">Export</button>}
        dense
      >
        <AppTable>
          <thead>
            <tr>
              <AppTableHeaderCell>Holding</AppTableHeaderCell>
              <AppTableHeaderCell numeric>Value</AppTableHeaderCell>
            </tr>
          </thead>
          <tbody>
            <tr>
              <AppTableCell>MSFT</AppTableCell>
              <AppTableCell numeric>€184.8K</AppTableCell>
            </tr>
          </tbody>
        </AppTable>
      </DataTableShell>
    );
    expect(screen.getByRole('heading', { name: 'Holdings' })).toBeInTheDocument();
    expect(screen.getByText('Active positions')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument();
    expect(screen.getByText('€184.8K')).toHaveClass('ui-app-table__cell--numeric');
    expect(container.querySelector('.ui-data-table-shell--dense')).toBeInTheDocument();
  });

  it('renders empty, loading, and error states', () => {
    const { rerender } = render(
      <DataTableShell empty emptyTitle="No transactions" emptyDescription="Try another filter." />
    );
    expect(screen.getByText('No transactions')).toBeInTheDocument();
    expect(screen.getByText('Try another filter.')).toBeInTheDocument();

    rerender(<DataTableShell loading loadingMessage="Loading transactions…" />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading transactions…');

    rerender(<DataTableShell error="Request failed" errorTitle="Table unavailable" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Table unavailable');
    expect(screen.getByRole('alert')).toHaveTextContent('Request failed');
  });
});

describe('SegmentedControl', () => {
  it('renders options and calls onChange with selected value', () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        ariaLabel="performance-metric"
        options={[
          { value: 'value', label: 'Value' },
          { value: 'twror', label: 'TWROR' },
        ]}
        value="value"
        onChange={onChange}
      />
    );
    expect(screen.getByRole('group', { name: 'performance-metric' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Value' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'TWROR' }));
    expect(onChange).toHaveBeenCalledWith('twror');
  });
});
