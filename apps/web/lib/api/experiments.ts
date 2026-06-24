import { apiRequest } from './client';

export type RunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface Experiment {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  goal: string | null;
  created_at: string;
}

export interface ExperimentRun {
  id: string;
  experiment_id: string;
  project_id: string;
  name: string;
  status: RunStatus;
  git_commit: string | null;
  command: string | null;
  config_json: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface Metric {
  name: string;
  step: number;
  value: number;
}

export interface ExperimentLog {
  seq: number;
  level: string;
  message: string;
  created_at: string;
}

export interface Artifact {
  id: string;
  name: string;
  artifact_type: string;
  uri: string;
  size_bytes: number | null;
  created_at: string;
}

const base = (p: string) => `/projects/${p}`;

export const listExperiments = (p: string): Promise<Experiment[]> =>
  apiRequest(`${base(p)}/experiments`);
export const createExperiment = (p: string, body: { name: string; description?: string; goal?: string }): Promise<Experiment> =>
  apiRequest(`${base(p)}/experiments`, { method: 'POST', body });
export const listRuns = (p: string, experimentId: string): Promise<ExperimentRun[]> =>
  apiRequest(`${base(p)}/experiments/${experimentId}/runs`);
export const listProjectRuns = (p: string): Promise<ExperimentRun[]> =>
  apiRequest(`${base(p)}/experiment-runs`);
export const getRun = (p: string, runId: string): Promise<ExperimentRun> =>
  apiRequest(`${base(p)}/experiment-runs/${runId}`);
export const listMetrics = (p: string, runId: string): Promise<Metric[]> =>
  apiRequest(`${base(p)}/experiment-runs/${runId}/metrics`);
export const listLogs = (p: string, runId: string): Promise<ExperimentLog[]> =>
  apiRequest(`${base(p)}/experiment-runs/${runId}/logs`);
export const listArtifacts = (p: string, runId: string): Promise<Artifact[]> =>
  apiRequest(`${base(p)}/experiment-runs/${runId}/artifacts`);
export const analyzeRun = (p: string, runId: string): Promise<{ agent_run_id: string }> =>
  apiRequest(`${base(p)}/experiment-runs/${runId}/analyze`, { method: 'POST' });
