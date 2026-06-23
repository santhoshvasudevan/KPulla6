/** Chart layout density presets for Executive Portfolio OS surfaces. */

export const CHART_DENSITY_VARIANTS = ['dashboard', 'analysis', 'compact'];

const DENSITY_CONFIG = {
  dashboard: {
    defaultHeight: 380,
    minTickGap: 32,
    shortRangeMinTickGap: 10,
    margin: { top: 12, right: 8, left: 0, bottom: 4 },
    grid: { vertical: false, horizontal: true },
    axisDetail: 'sparse',
    showLegend: true,
  },
  analysis: {
    defaultHeight: 320,
    minTickGap: 24,
    shortRangeMinTickGap: 8,
    margin: { top: 8, right: 16, left: 8, bottom: 8 },
    grid: { vertical: true, horizontal: true },
    axisDetail: 'detailed',
    showLegend: true,
  },
  compact: {
    defaultHeight: 120,
    minTickGap: 16,
    shortRangeMinTickGap: 6,
    margin: { top: 8, right: 24, left: 72, bottom: 8 },
    grid: { vertical: false, horizontal: true },
    axisDetail: 'minimal',
    showLegend: true,
  },
};

export function getChartDensity(variant = 'analysis') {
  return DENSITY_CONFIG[variant] ?? DENSITY_CONFIG.analysis;
}

export function getChartHeight(variant = 'analysis', override) {
  if (override != null) return override;
  return getChartDensity(variant).defaultHeight;
}

export function getChartMargin(variant = 'analysis', override) {
  if (override) return override;
  return getChartDensity(variant).margin;
}

export function getChartMinTickGap(variant = 'analysis', shortRange = false) {
  const density = getChartDensity(variant);
  return shortRange ? density.shortRangeMinTickGap : density.minTickGap;
}
