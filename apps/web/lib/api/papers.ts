import { apiRequest } from './client';

// --- Shared pagination -------------------------------------------------------
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// --- Ingestion vocabulary (backend `paper_ingest_status`) --------------------
export type IngestStatus = 'pending' | 'running' | 'succeeded' | 'abstract_only' | 'failed';

// --- Section vocabulary (backend `paper_section_kind`) -----------------------
export type SectionKind =
  | 'abstract'
  | 'introduction'
  | 'background'
  | 'method'
  | 'experiments'
  | 'results'
  | 'related_work'
  | 'conclusion'
  | 'appendix'
  | 'other';

/** One row of federated provenance, preserved in `PaperResult.extra.sources`. */
export interface Provenance {
  provider: string;
  external_id: string;
  url?: string;
  rank?: number;
}

/**
 * A federated search hit. `provenance` / `in_library` are NOT server fields —
 * they are derived client-side (from `extra.sources` and the library list).
 */
export interface PaperResult {
  source: string;
  external_id: string;
  title: string;
  abstract: string | null;
  authors: string[];
  venue: string | null;
  published_at: string | null;
  url: string;
  pdf_url: string | null;
  doi: string | null;
  citation_count: number | null;
  categories: string[];
  extra: Record<string, unknown>;
}

/** A library paper (backend `PaperResponse`). */
export interface Paper {
  id: string;
  project_id: string;
  source: string;
  external_id: string;
  title: string;
  abstract: string | null;
  authors_json: string[];
  venue: string | null;
  published_at: string | null;
  url: string;
  pdf_url: string | null;
  summary: string | null;
  doi: string | null;
  arxiv_id: string | null;
  primary_category: string | null;
  citation_count: number | null;
  ingest_status: IngestStatus;
  ingested_at: string | null;
  created_at: string;
}

export interface SearchFilters {
  categories?: string[];
  date_from?: string | null;
  date_to?: string | null;
  author?: string | null;
  title?: string | null;
  /** `sources` is intentionally omitted — the backend has no per-request source
   *  filter (CONSOLIDATION §7); the UI hides that control. */
  sort?: 'relevance' | 'latest';
  /** Pagination offset lives INSIDE filters (backend `PaperSearchFilters`). */
  offset?: number;
}

export interface SearchRequest {
  query: string;
  limit?: number;
  filters?: SearchFilters;
}

/** Raw backend response — `{results, provider_status}` only. */
export interface SearchResponse {
  results: PaperResult[];
  provider_status: Record<string, string>;
}

export interface ImportRef {
  source: string;
  external_id: string;
}

export type SkipReason = 'not_found' | 'provider_error' | 'invalid_source';

export interface SkippedImport {
  source: string;
  external_id: string;
  reason: SkipReason;
}

export interface ImportResponse {
  imported: Paper[];
  skipped: SkippedImport[];
}

export interface PaperSection {
  id?: string;
  seq: number;
  level: number;
  kind: SectionKind;
  heading: string;
  body: string;
  char_count: number;
}

export interface SectionsResponse {
  paper_id: string;
  ingest_status: IngestStatus;
  ingested_at: string | null;
  ingest_error: string | null;
  sections: PaperSection[];
}

export interface IngestTriggerResponse {
  paper_id: string;
  ingest_status: IngestStatus;
}

/** A freshness-feed item = `PaperResult` + server-computed `in_library`. */
export interface FeedItem extends PaperResult {
  in_library: boolean;
}

export interface FeedResponse {
  items: FeedItem[];
  next_cursor: string | null;
  categories_used: string[];
  cached: boolean;
}

export interface FeedCategories {
  categories: string[];
  derived: boolean;
}

// --- Derivation helpers (client-side; not server fields) ---------------------

/** Canonical citation key for a result/paper: `source:external_id`. */
export function citationKey(source: string, externalId: string): string {
  return `${source}:${externalId}`;
}

/** Provenance rows preserved by the federation merge in `extra.sources`. */
export function provenanceOf(result: PaperResult): Provenance[] {
  const raw = (result.extra as { sources?: unknown }).sources;
  if (!Array.isArray(raw)) {
    return [{ provider: result.source, external_id: result.external_id, url: result.url }];
  }
  return raw
    .filter((r): r is Record<string, unknown> => typeof r === 'object' && r !== null)
    .map((r) => ({
      provider: String(r.provider ?? r.source ?? ''),
      external_id: String(r.external_id ?? ''),
      url: typeof r.url === 'string' ? r.url : undefined,
      rank: typeof r.rank === 'number' ? r.rank : undefined,
    }))
    .filter((r) => r.provider);
}

// --- Papers ------------------------------------------------------------------
export function searchPapers(projectId: string, req: SearchRequest): Promise<SearchResponse> {
  return apiRequest(`/projects/${projectId}/papers/search`, {
    method: 'POST',
    body: { query: req.query, limit: req.limit ?? 20, filters: req.filters },
  });
}

/** Reference-based import — the server re-fetches authoritative metadata. */
export function importPapers(projectId: string, refs: ImportRef[]): Promise<ImportResponse> {
  return apiRequest(`/projects/${projectId}/papers/import`, {
    method: 'POST',
    body: { papers: refs.map((r) => ({ source: r.source, external_id: r.external_id })) },
  });
}

export function listPapers(
  projectId: string,
  opts: { limit?: number; offset?: number } = {},
): Promise<Page<Paper>> {
  const params = new URLSearchParams();
  if (opts.limit != null) params.set('limit', String(opts.limit));
  if (opts.offset != null) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return apiRequest(`/projects/${projectId}/papers${qs ? `?${qs}` : ''}`);
}

export function getPaper(projectId: string, paperId: string): Promise<Paper> {
  return apiRequest(`/projects/${projectId}/papers/${paperId}`);
}

export function deletePaper(projectId: string, paperId: string): Promise<void> {
  return apiRequest(`/projects/${projectId}/papers/${paperId}`, { method: 'DELETE' });
}

export function getPaperSections(projectId: string, paperId: string): Promise<SectionsResponse> {
  return apiRequest(`/projects/${projectId}/papers/${paperId}/sections`);
}

/** Re-ingest (also the "retry ingestion" action) → 202. */
export function reingestPaper(projectId: string, paperId: string): Promise<IngestTriggerResponse> {
  return apiRequest(`/projects/${projectId}/papers/${paperId}/ingest`, { method: 'POST' });
}

// --- Freshness feed ----------------------------------------------------------
export function getFeed(
  projectId: string,
  opts: { cursor?: string | null; limit?: number } = {},
): Promise<FeedResponse> {
  const params = new URLSearchParams();
  if (opts.cursor) params.set('cursor', opts.cursor);
  if (opts.limit != null) params.set('limit', String(opts.limit));
  const qs = params.toString();
  return apiRequest(`/projects/${projectId}/papers/feed${qs ? `?${qs}` : ''}`);
}

export function getFeedCategories(projectId: string): Promise<FeedCategories> {
  return apiRequest(`/projects/${projectId}/papers/feed/categories`);
}

export function putFeedCategories(projectId: string, categories: string[]): Promise<FeedCategories> {
  return apiRequest(`/projects/${projectId}/papers/feed/categories`, {
    method: 'PUT',
    body: { categories },
  });
}
