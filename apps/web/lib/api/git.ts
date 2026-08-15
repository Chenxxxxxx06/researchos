import { apiRequest } from './client';

export interface GitFileStatus {
  path: string;
  state: 'modified' | 'added' | 'deleted' | 'untracked' | 'renamed';
}

export interface GitStatus {
  provider: string;
  branch: string;
  clean: boolean;
  ahead: number;
  behind: number;
  files: GitFileStatus[];
}

/** One commit in the log (CONSOLIDATION §3 — producer shape). */
export interface GitCommitEntry {
  sha: string;
  author_name: string;
  author_email: string;
  authored_at: string;
  summary: string;
  patch_id: string | null;
  agent_run_id: string | null;
  reverts_sha: string | null;
  repository_snapshot_id: string | null;
  source_commit_sha: string | null;
}

export interface GitLogResponse {
  /** No `total`; has-more is inferred from page fill client-side. */
  entries: GitCommitEntry[];
}

export type GitDiffChangeType = 'added' | 'modified' | 'deleted' | 'renamed';

export interface GitCommitDiffFile {
  path: string;
  change_type: GitDiffChangeType;
  old_path: string | null;
  old_content: string | null;
  new_content: string | null;
  /** True when content was too large / binary and was omitted. */
  omitted: boolean;
  size: number;
}

export interface GitCommitDiff {
  sha: string;
  summary: string;
  author_name: string;
  authored_at: string;
  files: GitCommitDiffFile[];
}

export interface GitRevertResult {
  commit_sha: string;
  reverted_sha: string;
}

export interface RepositorySnapshot {
  id: string;
  project_id: string;
  idea_id: string;
  approved_by: string;
  source_url: string;
  source_owner: string;
  source_repo: string;
  destination_path: string;
  status: 'importing' | 'ready' | 'failed';
  commit_sha: string | null;
  default_branch: string | null;
  license_spdx: string | null;
  license_path: string | null;
  file_count: number;
  total_bytes: number;
  skipped_files_json: Array<{ path: string; reason: string }>;
  submodules_json: Array<{ name: string; path?: string; url?: string }>;
  manifest_hash: string | null;
  workspace_commit_sha: string | null;
  coding_session_id: string | null;
  coding_run_id: string | null;
  imported_at: string | null;
  error: string | null;
  created_at: string;
}

export interface StartRepositoryCodingResult {
  snapshot_id: string;
  coding_session_id: string;
  coding_run_id: string;
  stream: string;
}

/** Derive a short sha client-side (the log carries only full shas). */
export function shortSha(sha: string): string {
  return sha.slice(0, 7);
}

export function getGitStatus(projectId: string): Promise<GitStatus> {
  return apiRequest(`/projects/${projectId}/git/status`);
}

export function getGitLog(
  projectId: string,
  opts: { path?: string; limit?: number; skip?: number } = {},
): Promise<GitLogResponse> {
  const params = new URLSearchParams();
  if (opts.path) params.set('path', opts.path);
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.skip !== undefined) params.set('skip', String(opts.skip));
  const qs = params.toString();
  return apiRequest(`/projects/${projectId}/git/log${qs ? `?${qs}` : ''}`);
}

export function getCommitDiff(projectId: string, sha: string): Promise<GitCommitDiff> {
  return apiRequest(`/projects/${projectId}/git/commits/${sha}/diff`);
}

/** Non-destructive revert: creates an inverse commit. */
export function revertCommit(projectId: string, sha: string): Promise<GitRevertResult> {
  return apiRequest(`/projects/${projectId}/git/revert`, { method: 'POST', body: { sha } });
}

export function listRepositorySnapshots(
  projectId: string,
  ideaId?: string,
): Promise<RepositorySnapshot[]> {
  const params = new URLSearchParams();
  if (ideaId) params.set('idea_id', ideaId);
  const query = params.toString();
  return apiRequest(
    `/projects/${projectId}/git/repository-snapshots${query ? `?${query}` : ''}`,
  );
}

export function importRepositorySnapshot(
  projectId: string,
  body: { idea_id: string; github_url: string; approved: true },
): Promise<RepositorySnapshot> {
  return apiRequest(`/projects/${projectId}/git/repository-snapshots`, {
    method: 'POST',
    body,
  });
}

export function startRepositoryCoding(
  projectId: string,
  snapshotId: string,
): Promise<StartRepositoryCodingResult> {
  return apiRequest(
    `/projects/${projectId}/git/repository-snapshots/${snapshotId}/start-coding`,
    { method: 'POST' },
  );
}
