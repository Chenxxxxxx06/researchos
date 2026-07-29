import { apiRequest } from './client';

export type InboxSourceType = 'message' | 'note' | 'file' | 'audio_transcript';

export interface InboxItem {
  id: string;
  project_id: string;
  source_type: InboxSourceType;
  sender: string | null;
  title: string;
  content_text: string;
  original_filename: string | null;
  media_type: string | null;
  agent_run_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface CreateInboxItemInput {
  source_type: InboxSourceType;
  sender?: string | null;
  title: string;
  content_text: string;
  original_filename?: string | null;
  media_type?: string | null;
}

export function listInboxItems(projectId: string): Promise<InboxItem[]> {
  return apiRequest(`/projects/${projectId}/inbox`);
}

export function createInboxItem(
  projectId: string,
  input: CreateInboxItemInput,
): Promise<InboxItem> {
  return apiRequest(`/projects/${projectId}/inbox`, { method: 'POST', body: input });
}

export function analyzeInboxItem(
  projectId: string,
  itemId: string,
  mode: 'direction' | 'meeting_summary' | 'audio_to_paper' = 'direction',
): Promise<{ item_id: string; agent_run_id: string; status: string }> {
  return apiRequest(`/projects/${projectId}/inbox/${itemId}/analyze`, {
    method: 'POST',
    body: { mode },
  });
}
