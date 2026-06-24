import { apiRequest } from './client';

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
  extra: Record<string, unknown>;
}

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
  created_at: string;
}

export interface Idea {
  id: string;
  project_id: string;
  title: string;
  description: string;
  hypothesis: string | null;
  status: 'draft' | 'active' | 'archived';
  novelty_score: number | null;
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

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// --- Papers ------------------------------------------------------------------
export function searchPapers(
  projectId: string,
  query: string,
  limit = 10,
): Promise<{ results: PaperResult[] }> {
  return apiRequest(`/projects/${projectId}/papers/search`, {
    method: 'POST',
    body: { query, limit },
  });
}

export function importPapers(projectId: string, papers: PaperResult[]): Promise<Paper[]> {
  return apiRequest(`/projects/${projectId}/papers/import`, {
    method: 'POST',
    body: { papers },
  });
}

export function listPapers(projectId: string): Promise<Page<Paper>> {
  return apiRequest(`/projects/${projectId}/papers`);
}

// --- Ideas -------------------------------------------------------------------
export function listIdeas(projectId: string): Promise<Page<Idea>> {
  return apiRequest(`/projects/${projectId}/ideas`);
}

export function createIdea(
  projectId: string,
  body: { title: string; description?: string; hypothesis?: string },
): Promise<Idea> {
  return apiRequest(`/projects/${projectId}/ideas`, { method: 'POST', body });
}

export function runCriticReview(
  projectId: string,
  ideaId: string,
): Promise<{ agent_run_id: string; status: string; stream: string }> {
  return apiRequest(`/projects/${projectId}/ideas/${ideaId}/critic-review`, { method: 'POST' });
}

export function listCritiques(projectId: string, ideaId: string): Promise<Critique[]> {
  return apiRequest(`/projects/${projectId}/ideas/${ideaId}/critiques`);
}
