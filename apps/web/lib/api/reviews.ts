import { apiRequest } from './client';
import type { CreateAgentRunResponse } from './agents';

export interface ReviewSection {
  id: string;
  section_key: string;
  position: number;
  title: string;
  purpose: string;
  body: string;
  citations_json: string[];
  claims_json: Array<Record<string, unknown>>;
  status: 'outline' | 'draft' | 'needs_review' | 'approved';
  version: number;
  generated_by_run_id: string | null;
  updated_at: string;
}

export interface ReviewDocument {
  id: string;
  project_id: string;
  mission_id: string;
  title: string;
  status: string;
  version: number;
  citation_coverage: number;
  unsupported_claims: number;
  sections: ReviewSection[];
  created_at: string;
  updated_at: string;
}

export interface ReviewVersion {
  id: string;
  review_id: string;
  version: number;
  snapshot_json: Record<string, unknown>;
  source_type: string;
  source_run_id: string | null;
  created_by: string;
  created_at: string;
}

export function getReview(projectId: string, missionId: string) {
  return apiRequest<ReviewDocument>(`/projects/${projectId}/missions/${missionId}/review`);
}

export function generateReviewOutline(projectId: string, missionId: string, regenerate = false) {
  return apiRequest<ReviewDocument>(`/projects/${projectId}/missions/${missionId}/review/outline`, { method: 'POST', body: { regenerate } });
}

export function updateReviewSection(projectId: string, missionId: string, sectionId: string, input: { expected_version: number; title?: string; purpose?: string; body?: string; citations?: string[]; claims?: Array<Record<string, unknown>>; status?: ReviewSection['status'] }) {
  return apiRequest<ReviewDocument>(`/projects/${projectId}/missions/${missionId}/review/sections/${sectionId}`, { method: 'PUT', body: input });
}

export function generateReviewSection(projectId: string, missionId: string, sectionId: string, expectedVersion: number, regenerate = false) {
  return apiRequest<CreateAgentRunResponse>(`/projects/${projectId}/missions/${missionId}/review/sections/${sectionId}/generate`, {
    method: 'POST',
    body: { expected_version: expectedVersion, regenerate },
  });
}

export function listReviewVersions(projectId: string, missionId: string) {
  return apiRequest<ReviewVersion[]>(`/projects/${projectId}/missions/${missionId}/review/versions`);
}
