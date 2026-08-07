import { apiRequest } from './client';

export interface ManagementSummary {
  organization: { id: string; name: string; slug: string; plan: string };
  project: { id: string; name: string; description: string | null; field: string | null; status: string };
  researchers: Array<{ membership_id: string; user_id: string; display_name: string; email: string; role: string; is_active: boolean }>;
  papers: Array<{ id: string; title: string; source: string; year: number | null; ingest_status: string; doi: string | null; updated_at: string }>;
  experiment_plans: Array<{ id: string; mission_id: string; mission_topic: string; title: string; status: string; version: number; published_experiment_id: string | null; updated_at: string }>;
  reading_notes: Array<{ id: string; mission_id: string | null; paper_id: string; paper_title: string; note_type: string; content: string; updated_at: string }>;
  counts: { researchers: number; papers: number; experiment_plans: number; reading_notes: number; missions: number };
}

export const getManagementSummary = (projectId: string) =>
  apiRequest<ManagementSummary>(`/projects/${projectId}/manage/summary`);
