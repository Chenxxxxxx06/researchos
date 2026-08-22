import { apiRequest } from './client';

export type AutoDesignReleaseKind = 'poster' | 'slides' | 'website';

export interface AutoDesignArtifact {
  artifact_id: string;
  name: string;
  artifact_type: string;
  native_file_url?: string | null;
  native_format?: string | null;
  view_file_url?: string | null;
  view_format?: string | null;
  download_url?: string | null;
  pdf_url?: string | null;
  preview_url?: string | null;
  card_preview_url?: string | null;
  downloads?: Record<string, string>;
  quality_status?: 'ready' | 'ready_with_warnings' | null;
  quality_diagnostics?: string[];
}

export interface ReleaseJob {
  id: string;
  project_id: string;
  kind: AutoDesignReleaseKind;
  engine: string;
  model: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  external_run_id: string | null;
  artifact_json: {
    artifact?: AutoDesignArtifact | null;
    message?: { text?: string; failure?: { error_message?: string } | null };
  } | null;
  progress_json: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ReleaseIntegrationStatus {
  available: boolean;
  service_url: string;
  model: 'qwen-plus';
  message: string;
}

const base = (projectId: string) => `/projects/${projectId}/releases`;

export function getReleaseIntegration(projectId: string): Promise<ReleaseIntegrationStatus> {
  return apiRequest(`${base(projectId)}/integration`);
}

export function listReleaseJobs(projectId: string, limit = 20): Promise<ReleaseJob[]> {
  return apiRequest(`${base(projectId)}?limit=${limit}`);
}

export function createReleaseJob(
  projectId: string,
  input: { kind: AutoDesignReleaseKind; story_pack: string; template?: string },
): Promise<ReleaseJob> {
  return apiRequest(base(projectId), { method: 'POST', body: input });
}

export function getReleaseJob(projectId: string, jobId: string): Promise<ReleaseJob> {
  return apiRequest(`${base(projectId)}/${jobId}`);
}

export function cancelReleaseJob(projectId: string, jobId: string): Promise<ReleaseJob> {
  return apiRequest(`${base(projectId)}/${jobId}/cancel`, { method: 'POST' });
}
