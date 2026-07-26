import { apiRequest } from './client';
import type { AgentRunStatus, Page } from './agents';

/**
 * Coding chat client. Canonical route is `/coding-chat/sessions` with a
 * role-based message model (CONSOLIDATION §1): `GET /sessions/{sid}` returns the
 * session plus `messages[]`; a "turn" is a user message + the assistant message
 * sharing its `agent_run_id`. When the sessions route is absent (404/405) the UI
 * falls back to an implicit session built over `agent_runs` filtered to coding.
 */

export type ChatMessageRole = 'user' | 'assistant';

export interface ChatMessage {
  id: string;
  seq: number;
  role: ChatMessageRole;
  content: string;
  agent_run_id: string | null;
  patch_id: string | null;
  created_at: string;
}

export interface CodingSession {
  id: string;
  project_id: string;
  title: string;
  agent_type: string;
  created_at: string;
}

export interface CodingSessionDetail extends CodingSession {
  messages: ChatMessage[];
}

export interface CreateChatMessageResponse {
  message_id: string;
  agent_run_id: string;
  status: AgentRunStatus;
  stream: string;
}

/**
 * A chat turn: the view model the chat UI renders. Built client-side from
 * role-based messages (sessions mode) or from a coding agent run (fallback mode).
 */
export interface CodingTurn {
  agentRunId: string | null;
  seq: number;
  userMessage: string;
  /** Persisted assistant reply text (null while the run is still live). */
  assistantMessage: string | null;
  patchId: string | null;
  status: AgentRunStatus;
  error: string | null;
  createdAt: string;
}

const BASE = (projectId: string) => `/projects/${projectId}/coding-chat/sessions`;

export function listCodingSessions(
  projectId: string,
  opts: { limit?: number; offset?: number } = {},
): Promise<Page<CodingSession>> {
  const params = new URLSearchParams();
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.offset !== undefined) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return apiRequest(`${BASE(projectId)}${qs ? `?${qs}` : ''}`);
}

export function createCodingSession(projectId: string, title = ''): Promise<CodingSession> {
  return apiRequest(BASE(projectId), { method: 'POST', body: { title } });
}

export function getCodingSession(
  projectId: string,
  sessionId: string,
): Promise<CodingSessionDetail> {
  return apiRequest(`${BASE(projectId)}/${sessionId}`);
}

export function sendCodingMessage(
  projectId: string,
  sessionId: string,
  message: string,
): Promise<CreateChatMessageResponse> {
  return apiRequest(`${BASE(projectId)}/${sessionId}/messages`, {
    method: 'POST',
    body: { message },
  });
}

/**
 * Fallback send path (no session): spawns a bare coding run. Kept for the
 * implicit-session mode when the sessions route is unavailable.
 */
export function createCodingRun(
  projectId: string,
  message: string,
): Promise<{ agent_run_id: string; status: AgentRunStatus; stream: string }> {
  return apiRequest(`/projects/${projectId}/coding-agent/runs`, {
    method: 'POST',
    body: { message },
  });
}
