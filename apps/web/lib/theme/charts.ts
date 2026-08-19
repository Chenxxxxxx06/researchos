'use client';

/**
 * Chart theming for Recharts consumers.
 *
 * Static hex maps per resolved theme (no getComputedStyle → SSR-safe, no
 * layout reflow). Feature specs swap their hardcoded palettes for
 * `useChartTheme()` (see docs/DESIGN_TOKENS.md §7).
 */

import { useTheme } from './index';

/** Six categorical series colors per theme (dark set brightened). */
export const CHART_COLORS: { light: string[]; dark: string[] } = {
  light: ['#2563eb', '#0ea5e9', '#16a34a', '#d97706', '#f2645a', '#7c3aed'],
  dark: ['#5b8def', '#22d3ee', '#3ddc97', '#f5b83d', '#f2645a', '#a78bfa'],
};

export interface ChartTheme {
  colors: string[];
  grid: string;
  axis: string;
  tooltip: { background: string; border: string; color: string };
}

const LIGHT: ChartTheme = {
  colors: CHART_COLORS.light,
  grid: '#e6e8eb',
  axis: '#6b7280',
  tooltip: { background: '#ffffff', border: '#e6e8eb', color: '#18181b' },
};

const DARK: ChartTheme = {
  colors: CHART_COLORS.dark,
  grid: '#262b31',
  axis: '#9ba3ad',
  tooltip: { background: '#1b1f24', border: '#383e46', color: '#e8eaed' },
};

export function useChartTheme(): ChartTheme {
  const { resolved } = useTheme();
  return resolved === 'dark' ? DARK : LIGHT;
}
