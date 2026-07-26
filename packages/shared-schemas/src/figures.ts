/**
 * Result anchor / figure / style preset REST contracts (project-scoped;
 * CONSOLIDATION §5).
 *
 * Mirrors apps/api/researchos/figures/{enums,schemas,spec}.py.
 */

export type AnchorAggregation = 'final' | 'best' | 'min' | 'max' | 'mean';
export type FigureRenderStatus = 'pending' | 'rendering' | 'rendered' | 'failed';

// --- anchors -----------------------------------------------------------------

export interface AnchorResponse {
  id: string;
  name: string;
  /** Renderable macro including the backslash, e.g. "\\ROSMainAcc". */
  macro: string;
  experiment_id: string;
  /** null = follow the experiment's latest completed run. */
  run_id: string | null;
  metric_name: string;
  aggregation: AnchorAggregation;
  decimals: number;
  scale: number;
  suffix: string;
  captured_value: number | null;
  captured_run_id: string | null;
  captured_at: string | null;
  stale: boolean;
  created_at: string;
}

export interface RefreshedAnchorItem {
  id: string;
  name: string;
  value: number | null;
  formatted: string;
  run_id: string | null;
  resolved: boolean;
}

export interface RefreshAnchorsResponse {
  refreshed: number;
  unresolved: number;
  anchors: RefreshedAnchorItem[];
}

export interface AnchorStalenessItem {
  anchor_id: string;
  name: string;
  stale: boolean;
  captured_run_id: string | null;
  captured_value: number | null;
  latest_run_id: string | null;
  latest_value: number | null;
  delta: number | null;
  delta_pct: number | null;
}

/** GET /projects/{id}/anchors/staleness (polled; no staleness WS event). */
export interface AnchorStalenessReport {
  stale_count: number;
  items: AnchorStalenessItem[];
}

// --- figure spec (figures.spec_json) -----------------------------------------

export interface RunMetricSource {
  kind: 'run_metric';
  run_id?: string | null;
  experiment_id?: string | null;
  metric_name: string;
}

export interface InlineSource {
  kind: 'inline';
  points: [number, number][];
}

export type FigureSeriesSource = RunMetricSource | InlineSource;

export interface FigureSeries {
  source: FigureSeriesSource;
  label?: string | null;
  smoothing_window?: number;
}

export interface FigureSpec {
  chart: 'line' | 'bar' | 'scatter';
  series: FigureSeries[];
  title?: string | null;
  x_label?: string | null;
  y_label?: string | null;
  legend?: boolean;
  y_scale?: 'linear' | 'log';
  /** null = resolve from the creator's preferences at render time. */
  style_slug?: string | null;
}

// --- figures -----------------------------------------------------------------

export interface FigureResponse {
  id: string;
  name: string;
  spec: FigureSpec;
  status: FigureRenderStatus;
  stale: boolean;
  style_outdated: boolean;
  last_error: string | null;
  rendered_style_slug: string | null;
  rendered_style_version: string | null;
  source_run_ids: string[];
  last_rendered_at: string | null;
  latex_project_id: string | null;
  usage_path: string | null;
  created_at: string;
}

export interface RenderedAssetInfo {
  format: string;
  size_bytes: number;
  sha256: string;
}

export interface RenderFigureResponse {
  figure_id: string;
  status: FigureRenderStatus;
  assets: RenderedAssetInfo[];
}

// --- style presets -----------------------------------------------------------

/** Drives frontend SVG thumbnails (CONSOLIDATION §5). */
export interface StylePresetStyle {
  palette: string[];
  font_family: 'serif' | 'sans';
  grid: boolean;
  legend_frame: boolean;
}

/** GET /projects/{id}/figures/style-presets item. */
export interface StylePresetInfo {
  slug: string;
  version: string;
  name: string;
  description: string;
  palette: string[];
  style: StylePresetStyle;
}
