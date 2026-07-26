/**
 * Figures + style-presets API client (partition: frontend-paper).
 *
 * PROJECT-scoped per CONSOLIDATION §5 (`/projects/{id}/figures`, style presets
 * at `/projects/{id}/figures/style-presets`). Figure style lives INSIDE the spec
 * (`spec.style_slug`); re-styling = PATCH the spec then render. Assets are fetched
 * as bytes from `/figures/{id}/assets/{svg|png}` into blob URLs. Insert-into-paper
 * writes an \includegraphics block into the buffer + PATCH {latex_project_id,
 * usage_path}. Consumes the REAL backend (researchos/figures/{router,schemas}.py).
 */

import { API_BASE_URL, apiRequest } from './client';

export type FigureChart = 'line' | 'bar' | 'scatter';
export type FigureRenderStatus = 'pending' | 'rendering' | 'rendered' | 'failed';

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
  chart: FigureChart;
  series: FigureSeries[];
  title?: string | null;
  x_label?: string | null;
  y_label?: string | null;
  legend?: boolean;
  y_scale?: 'linear' | 'log';
  /** null = resolve from the creator's preferences at render time. */
  style_slug?: string | null;
}

export interface Figure {
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

export interface CreateFigureBody {
  name: string;
  spec: FigureSpec;
}

export interface UpdateFigureBody {
  name?: string;
  spec?: FigureSpec;
  latex_project_id?: string | null;
  usage_path?: string | null;
}

export interface RenderFigureResponse {
  figure_id: string;
  status: FigureRenderStatus;
  assets: { format: string; size_bytes: number; sha256: string }[];
}

/** The `style` object drives the client-side SVG thumbnails. */
export interface StylePresetStyle {
  palette: string[];
  font_family: 'serif' | 'sans';
  grid: boolean;
  legend_frame: boolean;
}

export interface StylePreset {
  slug: string;
  version: string;
  name: string;
  description: string;
  palette: string[];
  style: StylePresetStyle;
}

const base = (p: string) => `/projects/${p}/figures`;

export const listFigures = (p: string): Promise<Figure[]> => apiRequest(base(p));

export const getFigure = (p: string, figureId: string): Promise<Figure> =>
  apiRequest(`${base(p)}/${figureId}`);

export const createFigure = (p: string, body: CreateFigureBody): Promise<Figure> =>
  apiRequest(base(p), { method: 'POST', body });

export const updateFigure = (
  p: string,
  figureId: string,
  body: UpdateFigureBody,
): Promise<Figure> => apiRequest(`${base(p)}/${figureId}`, { method: 'PATCH', body });

export const deleteFigure = (p: string, figureId: string): Promise<void> =>
  apiRequest(`${base(p)}/${figureId}`, { method: 'DELETE' });

export const renderFigure = (
  p: string,
  figureId: string,
  mode: 'sync' | 'async' = 'async',
): Promise<RenderFigureResponse> =>
  apiRequest(`${base(p)}/${figureId}/render`, { method: 'POST', body: { mode } });

export const listStylePresets = (p: string): Promise<StylePreset[]> =>
  apiRequest(`${base(p)}/style-presets`);

/**
 * Fetch a rendered asset (png/svg) as an object URL. Cookie-authed, GET-only
 * (no CSRF). Throws on non-2xx so callers can render the placeholder box.
 */
export async function fetchFigureAssetUrl(
  p: string,
  figureId: string,
  fmt: 'png' | 'svg' = 'png',
): Promise<string> {
  const res = await fetch(`${API_BASE_URL}${base(p)}/${figureId}/assets/${fmt}`, {
    credentials: 'include',
    headers: { Accept: fmt === 'png' ? 'image/png' : 'image/svg+xml' },
  });
  if (!res.ok) throw new Error(`asset fetch failed: ${res.status}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
