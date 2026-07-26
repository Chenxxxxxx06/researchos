/**
 * LaTeX documents API client (partition: frontend-paper).
 *
 * Consumes the REAL backend routers (researchos/documents/{router,schemas}.py),
 * reconciled against CONSOLIDATION §8:
 *   - CAS save: 409 code is `document_version_conflict` (NOT `version_conflict`).
 *   - Tracked changes are server-side SUGGESTIONS (GET /suggestions, POST accept/reject);
 *     there is NO `/files/ops` route — selection edits go through `POST /selection-ops`.
 *   - Citations live at GET /citations + POST /citations/insert.
 *   - Compile response carries `preview_model` + `diagnostics` (both nullable).
 *
 * Every route the paper page consumes tolerates 404/422 as a designed degraded
 * state (queries use `retry: false`); this module only shapes requests/results.
 */

import { apiRequest, ApiError } from './client';
import { createAgentRun, type AgentRunContext, type CreateAgentRunResponse } from './agents';

// --- shared shapes -----------------------------------------------------------

export interface LatexProject {
  id: string;
  project_id: string;
  name: string;
  main_file_path: string;
  created_at: string;
}

export interface DocFileSummary {
  id: string;
  path: string;
  version: number;
}

export interface DocFile {
  id: string;
  path: string;
  content: string;
  version: number;
  updated_at: string;
}

/** 1-based positions (Monaco convention: line = lineNumber, col = column). */
export interface DocPosition {
  line: number;
  col: number;
}

export interface DocRange {
  start: DocPosition;
  end: DocPosition;
}

export type SuggestionOp =
  | 'rewrite'
  | 'expand'
  | 'condense'
  | 'fix_grammar'
  | 'continue_writing'
  | 'custom';

export type SuggestionStatus = 'proposed' | 'accepted' | 'rejected' | 'superseded';

export interface SuggestionSpan {
  kind: 'equal' | 'delete' | 'insert' | 'replace';
  old: string;
  new: string;
}

export interface Suggestion {
  id: string;
  path: string;
  op: SuggestionOp;
  status: SuggestionStatus;
  base_version: number;
  range: DocRange;
  old_text: string;
  new_text: string;
  rationale: string;
  spans: SuggestionSpan[];
  agent_run_id: string | null;
  last_error: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface SelectionOpResponse {
  agent_run_id: string;
  stream: string;
}

export interface AcceptSuggestionResponse {
  suggestion: Suggestion;
  file: DocFile;
}

// --- compile v2 --------------------------------------------------------------

export interface CompileDiagnostic {
  severity: 'error' | 'warning';
  code: string;
  message: string;
  file: string;
  line: number;
}

/** One structural block inside a preview section (kinds are open-ended). */
export interface PreviewBlock {
  kind: string; // 'paragraph' | 'math' | 'figure' | 'table' | 'list' | …
  text?: string;
  items?: string[];
  name?: string;
  caption?: string;
  asset_path?: string;
  file?: string;
  line?: number;
}

export interface PreviewSection {
  level?: number;
  number?: string;
  title?: string;
  file?: string;
  line?: number;
  blocks?: PreviewBlock[];
}

/** Backend types this as an untyped `dict`; we narrow the fields we render. */
export interface PreviewModel {
  title?: string;
  sections?: PreviewSection[];
  word_count?: number;
}

export interface CompileJob {
  id: string;
  latex_project_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  engine: string;
  log: string | null;
  preview: string | null;
  preview_model: PreviewModel | null;
  diagnostics: CompileDiagnostic[];
  error_summary: string | null;
  created_at: string;
  finished_at: string | null;
}

// --- citations & anchors -----------------------------------------------------

export interface CitationItem {
  paper_id: string;
  title: string;
  authors: string[];
  year: number | null;
  cite_key: string;
  in_bib: boolean;
}

export interface CitationListResponse {
  items: CitationItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface FileVersionRef {
  path: string;
  version: number;
}

export interface InsertCitationResponse {
  cite_key: string;
  snippet: string;
  bib_file: FileVersionRef;
  entry_added: boolean;
  bibliography_command_added: boolean;
}

export interface InsertAnchorResponse {
  snippet: string;
  include_added: boolean;
  validated: boolean;
  files: FileVersionRef[];
}

// --- version-conflict narrowing (CONSOLIDATION §8) ---------------------------
//
// The 409 code is `document_version_conflict`. `ApiError` does not retain the
// `details` body, so callers recover the server content by re-fetching the file
// (getFile) rather than reading it off the error — see MergeDialog.

export function isVersionConflict(err: unknown): err is ApiError {
  return err instanceof ApiError && err.code === 'document_version_conflict';
}

// --- endpoints ---------------------------------------------------------------

const base = (p: string) => `/projects/${p}/latex-projects`;

export const listLatexProjects = (p: string): Promise<LatexProject[]> => apiRequest(base(p));

export const createLatexProject = (p: string, name: string): Promise<LatexProject> =>
  apiRequest(base(p), { method: 'POST', body: { name } });

export const getLatexProject = (p: string, lid: string): Promise<LatexProject> =>
  apiRequest(`${base(p)}/${lid}`);

export const listFiles = (p: string, lid: string): Promise<DocFileSummary[]> =>
  apiRequest(`${base(p)}/${lid}/files`);

export const getFile = (p: string, lid: string, path: string): Promise<DocFile> =>
  apiRequest(`${base(p)}/${lid}/files/content?path=${encodeURIComponent(path)}`);

export interface SaveFileBody {
  path: string;
  content: string;
  /** Compare-and-swap; omit for the create/upsert path (new files). */
  expected_version?: number | null;
}

export const saveFile = (p: string, lid: string, body: SaveFileBody): Promise<DocFile> =>
  apiRequest(`${base(p)}/${lid}/files`, { method: 'PUT', body });

export interface ListSuggestionsOptions {
  status?: SuggestionStatus;
  path?: string;
  limit?: number;
  offset?: number;
}

export function listSuggestions(
  p: string,
  lid: string,
  opts: ListSuggestionsOptions = {},
): Promise<Page<Suggestion>> {
  const params = new URLSearchParams();
  if (opts.status) params.set('status', opts.status);
  if (opts.path) params.set('path', opts.path);
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.offset !== undefined) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return apiRequest(`${base(p)}/${lid}/suggestions${qs ? `?${qs}` : ''}`);
}

export const acceptSuggestion = (
  p: string,
  lid: string,
  suggestionId: string,
  expectedVersion?: number | null,
): Promise<AcceptSuggestionResponse> =>
  apiRequest(`${base(p)}/${lid}/suggestions/${suggestionId}/accept`, {
    method: 'POST',
    body: { expected_version: expectedVersion ?? null },
  });

export const rejectSuggestion = (
  p: string,
  lid: string,
  suggestionId: string,
): Promise<Suggestion> =>
  apiRequest(`${base(p)}/${lid}/suggestions/${suggestionId}/reject`, { method: 'POST' });

export interface CreateSelectionOpBody {
  op: SuggestionOp;
  path: string;
  range: DocRange;
  selection_text: string;
  expected_version?: number | null;
  instruction?: string;
}

export const createSelectionOp = (
  p: string,
  lid: string,
  body: CreateSelectionOpBody,
): Promise<SelectionOpResponse> =>
  apiRequest(`${base(p)}/${lid}/selection-ops`, { method: 'POST', body });

export const compile = (p: string, lid: string): Promise<CompileJob> =>
  apiRequest(`${base(p)}/${lid}/compile`, { method: 'POST' });

export const getCompileJob = (p: string, lid: string, jobId: string): Promise<CompileJob> =>
  apiRequest(`${base(p)}/${lid}/compile-jobs/${jobId}`);

export function listCitations(
  p: string,
  lid: string,
  opts: { limit?: number; offset?: number } = {},
): Promise<CitationListResponse> {
  const params = new URLSearchParams();
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.offset !== undefined) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return apiRequest(`${base(p)}/${lid}/citations${qs ? `?${qs}` : ''}`);
}

export interface InsertCitationBody {
  paper_id: string;
  bib_path?: string;
  expected_bib_version?: number | null;
  expected_main_version?: number | null;
}

export const insertCitation = (
  p: string,
  lid: string,
  body: InsertCitationBody,
): Promise<InsertCitationResponse> =>
  apiRequest(`${base(p)}/${lid}/citations/insert`, { method: 'POST', body });

export interface InsertAnchorBody {
  macro_name: string;
  target_path?: string;
  expected_version?: number | null;
  insert_at?: DocPosition | null;
}

export const insertAnchor = (
  p: string,
  lid: string,
  body: InsertAnchorBody,
): Promise<InsertAnchorResponse> =>
  apiRequest(`${base(p)}/${lid}/anchors/insert`, { method: 'POST', body });

/**
 * Whole-document assistant run. `agent_type: 'latex'` is a first-class member of
 * the AgentType union now (no cast needed) — kept behind this helper so the
 * paper feature has a single seam to the agents API.
 */
export const createLatexRun = (
  p: string,
  message: string,
  context?: AgentRunContext,
): Promise<CreateAgentRunResponse> =>
  createAgentRun(p, { agent_type: 'latex', message, context });
