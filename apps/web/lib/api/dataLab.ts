import type { CreateAgentRunResponse } from './agents';
import { apiRequest } from './client';

export interface DatasetColumn {
  name: string;
  type: 'text' | 'integer' | 'real' | 'boolean';
}

export interface DatasetSource {
  id: string;
  project_id: string;
  name: string;
  description: string;
  columns_json: DatasetColumn[];
  rows_json: Array<Record<string, unknown>>;
  created_by: string;
  created_at: string;
}

export interface SqlQueryResult {
  id: string;
  project_id: string;
  mission_id: string;
  dataset_source_id: string;
  agent_run_id: string;
  question: string;
  sql: string;
  explanation: string;
  columns_json: string[];
  rows_json: unknown[][];
  row_count: number;
  created_at: string;
}

export const listDatasetSources = (projectId: string) =>
  apiRequest<DatasetSource[]>(`/projects/${projectId}/datasets`);

export const createDatasetSource = (
  projectId: string,
  input: { name: string; description: string; columns: DatasetColumn[]; rows: Array<Record<string, unknown>> },
) => apiRequest<DatasetSource>(`/projects/${projectId}/datasets`, { method: 'POST', body: input });

export const runSqlQuestion = (
  projectId: string,
  missionId: string,
  datasetSourceId: string,
  question: string,
) => apiRequest<CreateAgentRunResponse>(`/projects/${projectId}/missions/${missionId}/sql-query`, {
  method: 'POST',
  body: { dataset_source_id: datasetSourceId, question },
});

export const listSqlResults = (projectId: string, missionId: string) =>
  apiRequest<SqlQueryResult[]>(`/projects/${projectId}/missions/${missionId}/sql-results`);
