/**
 * Experiment REST contracts.
 *
 * Mirrors apps/api/researchos/experiments/{enums,schemas}.py.
 */

export const EXPERIMENT_RUN_STATUSES = [
  'queued',
  'running',
  'completed',
  'failed',
  'cancelled',
] as const;
export type ExperimentRunStatus = (typeof EXPERIMENT_RUN_STATUSES)[number];

/** Per-metric metadata stored on experiments.metric_meta_json. */
export interface MetricMeta {
  direction: 'min' | 'max';
  unit?: string;
  display_name?: string;
}

/** GET/POST /projects/{id}/experiments/ingest-tokens item. */
export interface IngestTokenResponse {
  id: string;
  name: string;
  token_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

/** Creation response additionally carries the plaintext token (shown once). */
export interface IngestTokenCreatedResponse extends IngestTokenResponse {
  token: string;
}
