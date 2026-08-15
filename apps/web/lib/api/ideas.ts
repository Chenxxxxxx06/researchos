import type { CreateAgentRunResponse } from './agents';
import { apiRequest } from './client';
import type { Page } from './papers';

export type IdeaStatus = 'draft' | 'active' | 'archived';

export type GapType = 'coverage' | 'limitation' | 'transfer' | string;

/** Gap-generation fields live inside `IdeaResponse.metadata` (aliased server-side). */
export interface IdeaMetadata {
  generated?: boolean;
  gap_type?: GapType | null;
  supporting_paper_keys?: string[];
  evidence_basis?: 'reading_cards+parsed_sections' | string;
  reading_cards_used?: number;
  /** [method, problem] gap-cell label, when the idea came from a matrix cell. */
  cell?: [string, string];
  [key: string]: unknown;
}

export interface Idea {
  id: string;
  project_id: string;
  title: string;
  description: string;
  hypothesis: string | null;
  status: IdeaStatus;
  novelty_score: number | null;
  metadata: IdeaMetadata;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Critique {
  id: string;
  project_id: string;
  idea_id: string;
  agent_run_id: string | null;
  novelty_summary: string;
  weaknesses_json: string[];
  missing_baselines_json: string[];
  dataset_risks_json: string[];
  reproducibility_json: string[];
  citations_json: string[];
  created_at: string;
}

/** Synchronous generation result (backend `GenerateIdeasResponse`). */
export interface GenerateIdeasResponse {
  ideas: Idea[];
  gaps_considered: number;
  papers_used: number;
}

// --- Ideas -------------------------------------------------------------------
export function listIdeas(
  projectId: string,
  opts: { limit?: number; offset?: number } = {},
): Promise<Page<Idea>> {
  const params = new URLSearchParams();
  if (opts.limit != null) params.set('limit', String(opts.limit));
  if (opts.offset != null) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return apiRequest(`/projects/${projectId}/ideas${qs ? `?${qs}` : ''}`);
}

export function createIdea(
  projectId: string,
  body: { title: string; description?: string; hypothesis?: string },
): Promise<Idea> {
  return apiRequest(`/projects/${projectId}/ideas`, { method: 'POST', body });
}

export function updateIdea(
  projectId: string,
  ideaId: string,
  body: { title?: string; description?: string; hypothesis?: string; status?: IdeaStatus },
): Promise<Idea> {
  return apiRequest(`/projects/${projectId}/ideas/${ideaId}`, { method: 'PATCH', body });
}

/**
 * Synchronous gap-mining generation → returns the created ideas directly.
 * `409 library_too_small` when the library has fewer than 5 papers.
 */
export function generateIdeas(projectId: string, maxIdeas = 3): Promise<GenerateIdeasResponse> {
  return apiRequest(`/projects/${projectId}/ideas/generate`, {
    method: 'POST',
    body: { max_ideas: maxIdeas },
  });
}

export function runCriticReview(projectId: string, ideaId: string): Promise<CreateAgentRunResponse> {
  return apiRequest(`/projects/${projectId}/ideas/${ideaId}/critic-review`, { method: 'POST' });
}

export function listCritiques(projectId: string, ideaId: string): Promise<Critique[]> {
  return apiRequest(`/projects/${projectId}/ideas/${ideaId}/critiques`);
}
