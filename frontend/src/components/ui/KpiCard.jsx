import MetricCard from './MetricCard';

const TONE_BY_VARIANT = {
  neutral: 'neutral',
  success: 'positive',
  gain: 'positive',
  danger: 'negative',
  loss: 'negative',
  warning: 'warning',
  info: 'neutral',
};

export default function KpiCard({ variant = 'neutral', tone, ...props }) {
  return <MetricCard tone={tone ?? TONE_BY_VARIANT[variant] ?? 'neutral'} {...props} />;
}
