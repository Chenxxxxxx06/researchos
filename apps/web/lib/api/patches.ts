import { apiRequest } from './client';

export type PatchStatus = 'pending' | 'applied' | 'rejected' | 'conflict';
export type PatchChangeType = 'create' | 'modify' | 'delete';

export interface PatchFile {
  id: string;
  path: string;
  change_type: PatchChangeType;
  base_sha: string | null;
  new_content: string | null;
  hunks: unknown[];
}

export interface Patch {
  id: string;
  project_id: string;
  agent_run_id: string | null;
  created_by: string;
  status: PatchStatus;
  summary: string;
  created_at: string;
  applied_at: string | null;
  files: PatchFile[];
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface PatchConflict {
  path: string;
  expected_sha: string | null;
  actual_sha: string | null;
  reason: string;
}

export interface ApplyResult {
  patch_id: string;
  status: PatchStatus;
  conflicts: PatchConflict[];
}

export interface CreatePatchInput {
  summary: string;
  files: {
    path: string;
    change_type: PatchChangeType;
    base_sha?: string | null;
    new_content?: string | null;
  }[];
}

export function listPatches(projectId: string): Promise<Page<Patch>> {
  return apiRequest(`/projects/${projectId}/workspace/patches`);
}

export function getPatch(projectId: string, patchId: string): Promise<Patch> {
  return apiRequest(`/projects/${projectId}/workspace/patches/${patchId}`);
}

export function createPatch(projectId: string, input: CreatePatchInput): Promise<Patch> {
  return apiRequest(`/projects/${projectId}/workspace/patches`, { method: 'POST', body: input });
}

export function applyPatch(projectId: string, patchId: string): Promise<ApplyResult> {
  return apiRequest(`/projects/${projectId}/workspace/patches/${patchId}/apply`, {
    method: 'POST',
  });
}

export function rejectPatch(projectId: string, patchId: string): Promise<Patch> {
  return apiRequest(`/projects/${projectId}/workspace/patches/${patchId}/reject`, {
    method: 'POST',
  });
}
