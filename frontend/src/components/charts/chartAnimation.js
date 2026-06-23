/** Recharts animation props — subtle first render; respects reduced motion. */

export function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function getChartAnimationProps({ active = true, duration = 850 } = {}) {
  if (!active || prefersReducedMotion()) {
    return { isAnimationActive: false };
  }
  return {
    isAnimationActive: true,
    animationDuration: duration,
    animationEasing: 'ease-out',
  };
}
