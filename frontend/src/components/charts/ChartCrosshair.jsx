import { getChartCrosshairStroke } from './chartTheme';

/** Recharts Tooltip `cursor` props for vertical crosshair. */
export function getChartCrosshairCursorProps(variant = 'dashboard') {
  const stroke = getChartCrosshairStroke();
  if (variant === 'compact') {
    return { stroke, strokeWidth: 1, strokeDasharray: '4 4' };
  }
  return { stroke, strokeWidth: 1 };
}

/** Recharts Line/Area `activeDot` props for hover marker. */
export function getChartActiveDotProps(role = 'portfolio') {
  const base = {
    r: role === 'benchmark' ? 3 : 4,
    strokeWidth: 2,
  };
  if (role === 'muted') {
    return { ...base, r: 3, strokeOpacity: 0.8 };
  }
  return base;
}
