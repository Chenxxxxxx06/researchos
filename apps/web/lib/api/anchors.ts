/**
 * Result-anchors API client (partition: frontend-paper).
 *
 * PROJECT-scoped per CONSOLIDATION §5 (`/projects/{id}/anchors`, NOT
 * `/latex-projects/{lid}/result-bindings`). `AnchorResponse` uses
 * `decimals/scale/suffix` (not `format_spec`). Staleness is polled via
 * `GET /anchors/staleness`; there is no staleness WS event.
 *
 * Consumes the REAL backend (researchos/figures/{router,schemas}.py).
 */

import { apiRequest } from './client';

export type AnchorAggregation = 'final' | 'best' | 'min' | 'max' | 'mean';

export interface Anchor {
  id: string;
  name: string;
  /** Pre-formatted with backslash, e.g. "\\ROSBestAcc". */
  macro: string;
  experiment_id: string;
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

export interface CreateAnchorBody {
  name: string;
  experiment_id: string;
  run_id?: string | null;
  metric_name: string;
  aggregation?: AnchorAggregation;
  decimals?: number;
  scale?: number;
  suffix?: string;
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

export interface AnchorStalenessReport {
  stale_count: number;
  items: AnchorStalenessItem[];
}

const base = (p: string) => `/projects/${p}/anchors`;

export const listAnchors = (p: string): Promise<Anchor[]> => apiRequest(base(p));

export const createAnchor = (p: string, body: CreateAnchorBody): Promise<Anchor> =>
  apiRequest(base(p), { method: 'POST', body });

export const deleteAnchor = (p: string, anchorId: string): Promise<void> =>
  apiRequest(`${base(p)}/${anchorId}`, { method: 'DELETE' });

/** Re-resolve every anchor against current run data. */
export const refreshAnchors = (p: string): Promise<RefreshAnchorsResponse> =>
  apiRequest(`${base(p)}/refresh`, { method: 'POST', body: {} });

export const getAnchorStaleness = (p: string): Promise<AnchorStalenessReport> =>
  apiRequest(`${base(p)}/staleness`);

/** Human-readable "latest" vs pinned label for a staleness delta. */
export const formatDeltaPct = (pct: number | null): string =>
  pct === null ? '' : `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`;
