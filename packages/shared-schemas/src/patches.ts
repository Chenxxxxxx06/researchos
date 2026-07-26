/**
 * Patch proposal REST contracts.
 *
 * Mirrors apps/api/researchos/patches/{enums,schemas}.py. Hunks are
 * server-derived only (display); apply is file-granular (CONSOLIDATION §2).
 */

export type PatchStatus = 'pending' | 'applied' | 'rejected' | 'conflict';
export type PatchChangeType = 'create' | 'modify' | 'delete';

/** A raw search/replace block as proposed by the agent. */
export interface PatchEdit {
  search: string;
  replace: string;
}

/**
 * Input file for POST /projects/{id}/patches. `modify` requires `base_sha`
 * and exactly one of `new_content` | `edits`; hunks cannot be submitted.
 */
export interface PatchFileInput {
  path: string;
  change_type: PatchChangeType;
  base_sha?: string | null;
  new_content?: string | null;
  edits?: PatchEdit[] | null;
}

export interface CreatePatchRequest {
  summary?: string;
  files: PatchFileInput[];
}

/** Optional apply body: restrict the apply to a subset of file paths. */
export interface ApplyPatchRequest {
  paths?: string[] | null;
}

/** Server-computed unified-diff hunk (display only). */
export interface PatchHunk {
  header: string;
  old_start: number;
  old_lines: number;
  new_start: number;
  new_lines: number;
  content: string;
}

export interface PatchFile {
  id: string;
  path: string;
  change_type: PatchChangeType;
  base_sha: string | null;
  new_content: string | null;
  /** Full pre-image snapshot (null for create/binary/legacy rows). */
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

export interface PatchProposal {
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

/** POST /patches/{id}/apply response. */
export interface ApplyResult {
  patch_id: string;
  status: PatchStatus;
  conflicts: PatchConflict[];
  applied_commit_sha: string | null;
  skipped_paths: string[];
}
