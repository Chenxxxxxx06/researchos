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
  light: ['#2563eb', '#dc2626', '#16a34a', '#d97706', '#7c3aed', '#0891b2'],
  dark: ['#60a5fa', '#f87171', '#4ade80', '#fbbf24', '#a78bfa', '#22d3ee'],
};

export interface ChartTheme {
  colors: string[];
  grid: string;
  axis: string;
  tooltip: { background: string; border: string; color: string };
}

const LIGHT: ChartTheme = {
  colors: CHART_COLORS.light,
  grid: '#e5e5e5',
  axis: '#737373',
  tooltip: { background: '#ffffff', border: '#e5e5e5', color: '#171717' },
};

const DARK: ChartTheme = {
  colors: CHART_COLORS.dark,
  grid: '#2e2e33',
  axis: '#a1a1aa',
  tooltip: { background: '#1f1f23', border: '#3f3f46', color: '#f4f4f5' },
};

export function useChartTheme(): ChartTheme {
  const { resolved } = useTheme();
  return resolved === 'dark' ? DARK : LIGHT;
}
