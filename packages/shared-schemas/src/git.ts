/**
 * Git surface REST contracts (producer shapes; CONSOLIDATION §3).
 *
 * Mirrors apps/api/researchos/git/schemas.py. `short_sha` is derived
 * client-side; has-more is inferred from page fill (no totals).
 */

export type GitFileState = 'modified' | 'added' | 'deleted' | 'untracked' | 'renamed';

export interface GitFileStatus {
  path: string;
  state: GitFileState;
}

/** GET /projects/{id}/git/status. provider "disabled" = degrade to empty UI. */
export interface GitStatusResponse {
  provider: string;
  branch: string;
  clean: boolean;
  ahead: number;
  behind: number;
  files: GitFileStatus[];
}

export interface GitCommitEntry {
  sha: string;
  author_name: string;
  author_email: string;
  authored_at: string;
  summary: string;
  patch_id: string | null;
  agent_run_id: string | null;
  reverts_sha: string | null;
}

/** GET /projects/{id}/git/log?path=&limit=&skip=. */
export interface GitLogResponse {
  entries: GitCommitEntry[];
}

export interface GitCommitDiffFile {
  path: string;
  change_type: 'added' | 'modified' | 'deleted' | 'renamed';
  old_path: string | null;
  old_content: string | null;
  new_content: string | null;
  /** true when contents were omitted (binary/too large). */
  omitted: boolean;
  size: number;
}

/** GET /projects/{id}/git/commits/{sha}/diff. */
export interface GitCommitDiff {
  sha: string;
  summary: string;
  author_name: string;
  authored_at: string;
  files: GitCommitDiffFile[];
}

export interface GitRevertRequest {
  sha: string;
}

export interface GitRevertResponse {
  commit_sha: string;
  reverted_sha: string;
}

// --- workspace search (REST glue over the grep service; CONSOLIDATION §3) ----

export interface WorkspaceGrepMatch {
  path: string;
  line: number;
  preview: string;
}

/** GET /projects/{id}/workspace/grep?query=&regex=&limit=. */
export interface WorkspaceGrepResponse {
  matches: WorkspaceGrepMatch[];
  truncated: boolean;
}
