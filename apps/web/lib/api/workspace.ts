import { apiRequest } from './client';

export interface TreeNode {
  name: string;
  path: string;
  type: 'file' | 'dir';
  children?: TreeNode[];
}

export interface TreeResponse {
  root: string;
  nodes: TreeNode[];
}

export interface FileContent {
  path: string;
  binary: boolean;
  too_large: boolean;
  size: number;
  sha: string | null;
  content: string | null;
}

export interface GrepMatch {
  path: string;
  line: number;
  preview: string;
}

export interface GrepResponse {
  matches: GrepMatch[];
  truncated: boolean;
}

export function getTree(projectId: string): Promise<TreeResponse> {
  return apiRequest(`/projects/${projectId}/workspace/tree`);
}

export function getFile(projectId: string, path: string): Promise<FileContent> {
  return apiRequest(`/projects/${projectId}/workspace/files?path=${encodeURIComponent(path)}`);
}

export function saveFile(
  projectId: string,
  input: { path: string; content: string; base_sha: string | null },
): Promise<FileContent> {
  return apiRequest(`/projects/${projectId}/workspace/files`, {
    method: 'PUT',
    body: input,
  });
}

export interface TerminalRunResult {
  argv: string[];
  cwd: string;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  duration_ms: number;
  timed_out: boolean;
}

export function runTerminalCommand(
  projectId: string,
  input: { argv: string[]; cwd?: string; timeout_seconds?: number },
): Promise<TerminalRunResult> {
  return apiRequest(`/projects/${projectId}/workspace/terminal/run`, {
    method: 'POST',
    body: {
      argv: input.argv,
      cwd: input.cwd ?? '.',
      timeout_seconds: input.timeout_seconds ?? 30,
    },
  });
}

/**
 * Full-text workspace search. Literal by default; pass `regex:true` for a
 * regular expression (400 `code:'validation_error'` on an invalid pattern).
 * A 404 means the endpoint is absent — callers hide the Search tab.
 */
export function grepWorkspace(
  projectId: string,
  opts: { query: string; regex?: boolean; limit?: number },
): Promise<GrepResponse> {
  const params = new URLSearchParams();
  params.set('query', opts.query);
  if (opts.regex) params.set('regex', 'true');
  params.set('limit', String(opts.limit ?? 100));
  return apiRequest(`/projects/${projectId}/workspace/grep?${params.toString()}`);
}
