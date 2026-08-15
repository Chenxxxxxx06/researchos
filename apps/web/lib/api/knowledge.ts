import { apiRequest } from './client';
import type { CreateAgentRunResponse } from './agents';

export interface MissionPaper {
  id: string;
  paper_id: string;
  cluster_id: string | null;
  relevance_score: number | null;
  inclusion_reason: string;
  title: string;
  authors: Array<{ name?: string } | string>;
  venue: string | null;
  published_at: string | null;
  ingest_status: string;
}

export interface TopicCluster {
  id: string;
  mission_id: string;
  name: string;
  summary: string;
  keywords_json: string[];
  position: number;
  version: number;
  paper_count: number;
  created_at: string;
  updated_at: string;
}

export interface RagHit {
  chunk_id: string | null;
  paper_id: string;
  section_id: string | null;
  title: string;
  heading: string;
  kind: string | null;
  snippet: string;
  score: number;
  vector_score: number;
  keyword_score: number;
  char_start: number | null;
  char_end: number | null;
  citation_key: string;
}

export interface RagSearchResponse {
  query: string;
  mode: string;
  embedding_model: string;
  indexed_papers: number;
  indexed_chunks: number;
  hits: RagHit[];
}

export interface ReadingCard {
  id: string;
  project_id: string;
  mission_id: string;
  paper_id: string;
  summary: string;
  research_question: string;
  reading_focus_json: string[];
  method_flow_json: string[];
  experimental_setup_json: string[];
  key_results_json: string[];
  conclusions_json: string[];
  strengths_json: string[];
  limitations_json: string[];
  reproducibility_json: string[];
  claims_json: Array<Record<string, unknown>>;
  status: 'draft' | 'needs_review' | 'reviewed';
  version: number;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReadingNote {
  id: string;
  project_id: string;
  mission_id: string | null;
  paper_id: string;
  section_id: string | null;
  quote: string;
  content: string;
  tags_json: string[];
  version: number;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export function listMissionPapers(projectId: string, missionId: string) {
  return apiRequest<MissionPaper[]>(`/projects/${projectId}/missions/${missionId}/papers`);
}

export function addMissionPapers(projectId: string, missionId: string, paperIds: string[]) {
  return apiRequest<MissionPaper[]>(`/projects/${projectId}/missions/${missionId}/papers`, {
    method: 'POST',
    body: { paper_ids: paperIds },
  });
}

export function listTopicClusters(projectId: string, missionId: string) {
  return apiRequest<TopicCluster[]>(`/projects/${projectId}/missions/${missionId}/clusters`);
}

export function generateTopicClusters(projectId: string, missionId: string) {
  return apiRequest<TopicCluster[]>(`/projects/${projectId}/missions/${missionId}/cluster`, {
    method: 'POST',
  });
}

export function ragSearch(projectId: string, query: string, limit = 12) {
  return apiRequest<RagSearchResponse>(`/projects/${projectId}/rag/search`, {
    method: 'POST',
    body: { query, limit },
  });
}

export function listReadingCards(projectId: string, missionId: string) {
  return apiRequest<ReadingCard[]>(`/projects/${projectId}/missions/${missionId}/reading-cards`);
}

export function saveReadingCard(
  projectId: string,
  paperId: string,
  payload: {
    mission_id: string;
    expected_version?: number;
    summary: string;
    research_question: string;
    reading_focus: string[];
    method_flow: string[];
    experimental_setup: string[];
    key_results: string[];
    conclusions: string[];
    strengths: string[];
    limitations: string[];
    reproducibility: string[];
    claims: Array<Record<string, unknown>>;
    status: ReadingCard['status'];
  },
) {
  return apiRequest<ReadingCard>(`/projects/${projectId}/papers/${paperId}/reading-card`, {
    method: 'PUT',
    body: payload,
  });
}

export function generateReadingCard(
  projectId: string,
  paperId: string,
  missionId: string,
  regenerate: boolean,
  sectionKinds: string[],
) {
  return apiRequest<CreateAgentRunResponse>(
    `/projects/${projectId}/papers/${paperId}/reading-card/generate`,
    { method: 'POST', body: { mission_id: missionId, regenerate, section_kinds: sectionKinds } },
  );
}

export function listReadingNotes(projectId: string, paperId: string, missionId?: string | null) {
  const query = missionId ? `?mission_id=${encodeURIComponent(missionId)}` : '';
  return apiRequest<ReadingNote[]>(`/projects/${projectId}/papers/${paperId}/notes${query}`);
}

export function createReadingNote(
  projectId: string,
  paperId: string,
  input: { mission_id?: string | null; section_id?: string | null; quote?: string; content: string; tags?: string[] },
) {
  return apiRequest<ReadingNote>(`/projects/${projectId}/papers/${paperId}/notes`, {
    method: 'POST',
    body: input,
  });
}

export function deleteReadingNote(projectId: string, noteId: string) {
  return apiRequest<void>(`/projects/${projectId}/notes/${noteId}`, { method: 'DELETE' });
}
