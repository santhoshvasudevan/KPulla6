import { SectionCard } from '../ui';
import './metricSheet.css';

export default function MetricSheetSection({
  title = 'Metric Sheet',
  subtitle,
  actions,
  children,
  className = '',
  compact = false,
  id,
}) {
  return (
    <SectionCard
      id={id}
      title={title}
      subtitle={subtitle}
      actions={actions}
      className={['metric-sheet', className].filter(Boolean).join(' ')}
      compact={compact}
    >
      {children}
    </SectionCard>
  );
}
