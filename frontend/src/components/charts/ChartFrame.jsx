import { ChartCard } from '../ui';
import { getChartHeight } from './chartDensity';
import {
  ChartEmptyState,
  ChartErrorState,
  ChartLoadingState,
  ChartPartialState,
} from './ChartStates';
import './charts.css';

/**
 * Shared chart shell: ChartCard + standardized states + density-aware panel.
 * Children should render Recharts content only; no finance calculations here.
 */
export default function ChartFrame({
  title,
  subtitle,
  toolbar,
  status,
  legend,
  footer,
  density = 'analysis',
  height,
  loading = false,
  loadingMessage = 'Loading chart…',
  error,
  errorTitle = 'Chart unavailable',
  onRetry,
  empty = false,
  emptyTitle = 'No chart data',
  emptyDescription,
  emptyAction,
  emptyVariant = 'card',
  partialMessage,
  children,
  className = '',
  compact = false,
  panelClassName = '',
}) {
  const chartHeight = getChartHeight(density, height);
  const panelClasses = [
    'ui-chart-frame__panel',
    `ui-chart-frame__panel--${density}`,
    panelClassName,
  ]
    .filter(Boolean)
    .join(' ');

  let body = children;
  if (loading) {
    body = <ChartLoadingState message={loadingMessage} />;
  } else if (error) {
    body = <ChartErrorState title={errorTitle} message={error} onRetry={onRetry} />;
  } else if (empty) {
    body = (
      <ChartEmptyState
        title={emptyTitle}
        description={emptyDescription}
        action={emptyAction}
        variant={emptyVariant}
      />
    );
  } else {
    body = (
      <div className={panelClasses} style={{ minHeight: chartHeight }}>
        {partialMessage ? <ChartPartialState message={partialMessage} /> : null}
        {children}
      </div>
    );
  }

  return (
    <ChartCard
      title={title}
      subtitle={subtitle}
      toolbar={toolbar}
      status={status}
      legend={legend}
      footer={footer}
      compact={compact}
      className={['ui-chart-frame', className].filter(Boolean).join(' ')}
    >
      {body}
    </ChartCard>
  );
}
