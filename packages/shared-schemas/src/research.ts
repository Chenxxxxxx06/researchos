/**
 * Research surface vocabulary (CONSOLIDATION §7).
 *
 * Mirrors apps/api/researchos/research/enums.py. There is no `full_text`
 * string anywhere; papers expose typed sections instead.
 */

export const PAPER_INGEST_STATUSES = [
  'pending',
  'running',
  'succeeded',
  'abstract_only',
  'failed',
] as const;
export type PaperIngestStatus = (typeof PAPER_INGEST_STATUSES)[number];

export const PAPER_SECTION_KINDS = [
  'abstract',
  'introduction',
  'background',
  'method',
  'experiments',
  'results',
  'related_work',
  'conclusion',
  'appendix',
  'other',
] as const;
export type PaperSectionKind = (typeof PAPER_SECTION_KINDS)[number];

export interface PaperSectionItem {
  seq: number;
  level: number;
  kind: PaperSectionKind;
  heading: string;
  body: string;
  char_count: number;
}

/** GET /projects/{id}/papers/{paper_id}/sections. */
export interface PaperSectionsResponse {
  paper_id: string;
  ingest_status: PaperIngestStatus;
  ingested_at: string | null;
  ingest_error: string | null;
  sections: PaperSectionItem[];
}
