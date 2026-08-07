import type { CreateAgentRunResponse } from './agents';
import { apiRequest } from './client';

export interface CitationAuditItem {
  paper_id: string;
  citation_key: string;
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  arxiv_id: string | null;
  url: string;
  missing_fields: string[];
  status: 'complete' | 'needs_metadata';
}

export interface CitationAudit {
  id: string;
  project_id: string;
  mission_id: string;
  agent_run_id: string;
  items_json: CitationAuditItem[];
  duplicate_groups_json: Array<{ match_key: string; paper_ids: string[]; count: number }>;
  missing_field_count: number;
  bibtex_text: string;
  created_by: string;
  created_at: string;
}

const path = (projectId: string, missionId: string) =>
  `/projects/${projectId}/missions/${missionId}/citation-audits`;

export const listCitationAudits = (projectId: string, missionId: string) =>
  apiRequest<CitationAudit[]>(path(projectId, missionId));

export const runCitationAudit = (projectId: string, missionId: string) =>
  apiRequest<CreateAgentRunResponse>(path(projectId, missionId), { method: 'POST' });
