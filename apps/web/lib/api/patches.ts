import { apiRequest } from './client';

export type PatchStatus = 'pending' | 'applied' | 'rejected' | 'conflict';
export type PatchChangeType = 'create' | 'modify' | 'delete';

/** Server-computed unified hunk (CONSOLIDATION §2). No client-assignable id. */
export interface PatchHunk {
  header: string;
  old_start: number;
  old_lines: number;
  new_start: number;
  new_lines: number;
  /** `@@`-prefixed unified body. */
  content: string;
}

export interface PatchEdit {
  search: string;
  replace: string;
}

export interface PatchFile {
  id: string;
  path: string;
  change_type: PatchChangeType;
  base_sha: string | null;
  new_content: string | null;
  /** Recorded base at proposal time; null for create/legacy payloads. */
  base_content: string | null;
  edits: PatchEdit[];
  hunks: PatchHunk[];
}

export interface PatchConflict {
  path: string;
  expected_sha: string | null;
  actual_sha: string | null;
  reason: string;
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
  applied_commit_sha: string | null;
  conflicts: PatchConflict[];
  superseded_by: string | null;
  files: PatchFile[];
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApplyResult {
  patch_id: string;
  status: PatchStatus;
  conflicts: PatchConflict[];
  applied_commit_sha: string | null;
  /** Paths that were not applied (partial apply, file-granularity). */
  skipped_paths: string[];
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

export function listPatches(
  projectId: string,
  opts: { limit?: number; offset?: number } = {},
): Promise<Page<Patch>> {
  const params = new URLSearchParams();
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.offset !== undefined) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return apiRequest(`/projects/${projectId}/workspace/patches${qs ? `?${qs}` : ''}`);
}

export function getPatch(projectId: string, patchId: string): Promise<Patch> {
  return apiRequest(`/projects/${projectId}/workspace/patches/${patchId}`);
}

export function createPatch(projectId: string, input: CreatePatchInput): Promise<Patch> {
  return apiRequest(`/projects/${projectId}/workspace/patches`, { method: 'POST', body: input });
}

/**
 * Apply a patch. With `paths` omitted, applies all files (today's semantics).
 * With `paths`, restricts the apply to that subset (file-granularity partial
 * apply); the response reports `skipped_paths`. If the backend does not support
 * the body it responds 422 `code:'unsupported'` — callers hide the checkboxes.
 */
export function applyPatch(
  projectId: string,
  patchId: string,
  paths?: string[],
): Promise<ApplyResult> {
  return apiRequest(`/projects/${projectId}/workspace/patches/${patchId}/apply`, {
    method: 'POST',
    body: paths && paths.length > 0 ? { paths } : undefined,
  });
}

export function rejectPatch(projectId: string, patchId: string): Promise<Patch> {
  return apiRequest(`/projects/${projectId}/workspace/patches/${patchId}/reject`, {
    method: 'POST',
  });
}
