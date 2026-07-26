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
