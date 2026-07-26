/**
 * LaTeX document REST contracts.
 *
 * Mirrors apps/api/researchos/documents/{enums,schemas,service,merge,latex_parse}.py.
 */

export type CompileStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export const SELECTION_OPS = [
  'rewrite',
  'expand',
  'condense',
  'fix_grammar',
  'continue_writing',
  'custom',
] as const;
export type SelectionOp = (typeof SELECTION_OPS)[number];

export type SuggestionStatus = 'proposed' | 'accepted' | 'rejected' | 'superseded';

export interface Position {
  /** 1-based. */
  line: number;
  /** 1-based. */
  col: number;
}

export interface TextRange {
  start: Position;
  end: Position;
}

// --- files -------------------------------------------------------------------

export interface DocumentFileResponse {
  id: string;
  path: string;
  content: string;
  version: number;
  updated_at: string;
}

export interface FileVersionRef {
  path: string;
  version: number;
}

export interface FileRevisionSummary {
  version: number;
  updated_by: string | null;
  created_at: string;
}

// --- selection ops / suggestions --------------------------------------------

/** POST /projects/{pid}/latex-projects/{lid}/selection-ops body. */
export interface SelectionOpRequest {
  op: SelectionOp;
  path: string;
  range: TextRange;
  selection_text?: string;
  expected_version?: number | null;
  instruction?: string | null;
}

/** 202 response; completion arrives via agent.run.completed (or run polling). */
export interface SelectionOpResponse {
  agent_run_id: string;
  stream: string;
}

export interface SuggestionSpan {
  kind: 'equal' | 'delete' | 'insert' | 'replace';
  old: string;
  new: string;
}

/** A server-side tracked-change suggestion awaiting review. */
export interface DocumentSuggestion {
  id: string;
  path: string;
  op: SelectionOp;
  status: SuggestionStatus;
  base_version: number;
  range: TextRange;
  old_text: string;
  new_text: string;
  rationale: string;
  spans: SuggestionSpan[];
  agent_run_id: string | null;
  last_error: string | null;
  created_at: string;
  resolved_at: string | null;
}

/** POST /suggestions/{id}/accept response: updated file replaces the buffer. */
export interface AcceptSuggestionResponse {
  suggestion: DocumentSuggestion;
  file: DocumentFileResponse;
}

// --- save conflict (409 document_version_conflict details) -------------------

export interface MergeConflictRegion {
  base_start: number;
  base_end: number;
  base_text: string;
  server_text: string;
  client_text: string;
}

/** Three-way merge hint; merged_content is set only when clean. */
export interface MergeHint {
  clean: boolean;
  merged_content: string | null;
  conflicts: MergeConflictRegion[];
}

/** details payload of the 409 error with code "document_version_conflict". */
export interface DocumentVersionConflictDetails {
  path: string;
  expected_version: number;
  current_version: number;
  /** true when server_content was omitted for size; refetch the file instead. */
  server_content_omitted: boolean;
  server_content?: string;
  base_available: boolean;
  merge: MergeHint | null;
}

// --- compile -----------------------------------------------------------------

export interface CompileDiagnostic {
  severity: 'error' | 'warning';
  code: string;
  message: string;
  file: string;
  line: number;
}

export type PreviewBlockKind = 'paragraph' | 'math' | 'figure' | 'table' | 'list';

export interface PreviewBlock {
  kind: PreviewBlockKind;
  text: string;
  file: string;
  line: number;
}

export interface PreviewSection {
  level: number;
  number: string;
  title: string;
  file: string;
  line: number;
  blocks: PreviewBlock[];
}

/** Structural preview model produced by the mock compile parse (writing D7). */
export interface PreviewModel {
  title: string | null;
  sections: PreviewSection[];
  labels: string[];
  bib_keys: string[];
  word_count: number;
}

export interface CompileJobResponse {
  id: string;
  latex_project_id: string;
  status: CompileStatus;
  engine: string;
  log: string | null;
  preview: string | null;
  preview_model: PreviewModel | null;
  diagnostics: CompileDiagnostic[];
  error_summary: string | null;
  created_at: string;
  finished_at: string | null;
}

// --- citations ---------------------------------------------------------------

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
