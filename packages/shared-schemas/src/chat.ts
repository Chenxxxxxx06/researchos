/**
 * Coding chat REST contracts (CONSOLIDATION §1).
 *
 * Mirrors apps/api/researchos/coding_chat/schemas.py. Routes live under
 * /projects/{project_id}/coding-chat/sessions. A "turn" = a user message plus
 * the assistant message sharing its agent_run_id; there is no /turns route.
 */

import type { AgentRunStatus, AgentType } from './agents';

export interface ChatSession {
  id: string;
  project_id: string;
  title: string;
  agent_type: AgentType;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  seq: number;
  role: 'user' | 'assistant';
  content: string;
  agent_run_id: string | null;
  patch_id: string | null;
  created_at: string;
}

/** GET /sessions/{sid}: session plus ordered messages. */
export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export interface CreateChatSessionRequest {
  title?: string;
}

/**
 * POST /sessions/{sid}/messages body. Returns 409
 * {"error":{"code":"session_busy"}} while the latest run is queued/running.
 */
export interface CreateChatMessageRequest {
  message: string;
}

export interface CreateChatMessageResponse {
  message_id: string;
  agent_run_id: string;
  status: AgentRunStatus;
  stream: string;
}
