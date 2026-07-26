import { apiRequest } from './client';

/**
 * Agent types accepted by the runtime. Kept as a superset of the backend
 * `AgentType` enum (research/critic/coding/latex/experiment) so cross-partition
 * consumers (coding chat fallback, research chat) need no casts. There is
 * deliberately no `ideate` member — idea generation is a synchronous REST call.
 */
export type AgentType = 'research' | 'critic' | 'coding' | 'latex' | 'experiment';
export type AgentRunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface AgentRun {
  id: string;
  project_id: string;
  user_id: string;
  agent_type: AgentType;
  status: AgentRunStatus;
  input_json: { message?: string; context?: Record<string, unknown> };
  output_json:
    | ({
        message?: string;
        novelty_summary?: string;
        citations?: string[];
        /** Present on coding runs that finalized a patch proposal. */
        patch_id?: string | null;
      } & Record<string, unknown>)
    | null;
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

/** Context accepted by the runtime for seeding an agent run (frontend-research CP-2). */
export interface AgentRunContext {
  idea_id?: string;
  paper_id?: string;
  section_seqs?: number[];
}

export function createAgentRun(
  projectId: string,
  body: { agent_type: AgentType; message: string; context?: AgentRunContext },
): Promise<CreateAgentRunResponse> {
  return apiRequest(`/projects/${projectId}/agents/runs`, { method: 'POST', body });
}

export interface ListAgentRunsOptions {
  limit?: number;
  offset?: number;
}

export function listAgentRuns(
  projectId: string,
  opts: ListAgentRunsOptions = {},
): Promise<Page<AgentRun>> {
  const params = new URLSearchParams();
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.offset !== undefined) params.set('offset', String(opts.offset));
  const qs = params.toString();
  return apiRequest(`/projects/${projectId}/agents/runs${qs ? `?${qs}` : ''}`);
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

/** Cancel a live run (STRETCH: cancel button on a live turn). */
export function cancelAgentRun(projectId: string, runId: string): Promise<AgentRun> {
  return apiRequest(`/projects/${projectId}/agents/runs/${runId}/cancel`, { method: 'POST' });
}
