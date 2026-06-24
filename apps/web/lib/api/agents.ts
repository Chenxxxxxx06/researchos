import { apiRequest } from './client';

export type AgentType = 'research' | 'critic';
export type AgentRunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface AgentRun {
  id: string;
  project_id: string;
  user_id: string;
  agent_type: AgentType;
  status: AgentRunStatus;
  input_json: { message?: string; context?: Record<string, unknown> };
  output_json: {
    message?: string;
    novelty_summary?: string;
    citations?: string[];
  } | null;
  error_json: { message?: string } | null;
  token_usage_json: Record<string, number>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface CreateAgentRunResponse {
  agent_run_id: string;
  status: AgentRunStatus;
  stream: string;
}

export interface AgentRunEvent {
  seq: number;
  event_type: string;
  payload_json: Record<string, unknown>;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export function createAgentRun(
  projectId: string,
  body: { agent_type: AgentType; message: string; context?: { idea_id?: string } },
): Promise<CreateAgentRunResponse> {
  return apiRequest(`/projects/${projectId}/agents/runs`, { method: 'POST', body });
}

export function listAgentRuns(projectId: string): Promise<Page<AgentRun>> {
  return apiRequest(`/projects/${projectId}/agents/runs`);
}

export function getAgentRun(projectId: string, runId: string): Promise<AgentRun> {
  return apiRequest(`/projects/${projectId}/agents/runs/${runId}`);
}

export function getAgentRunEvents(
  projectId: string,
  runId: string,
  afterSeq = -1,
): Promise<AgentRunEvent[]> {
  return apiRequest(`/projects/${projectId}/agents/runs/${runId}/events?after_seq=${afterSeq}`);
}
