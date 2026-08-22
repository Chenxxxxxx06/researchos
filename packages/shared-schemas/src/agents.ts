/**
 * Agent vocabulary shared by REST and WebSocket contracts.
 *
 * Mirrors apps/api/researchos/agents/enums.py.
 */

export const AGENT_TYPES = [
  'research',
  'critic',
  'coding',
  'experiment',
  'latex',
  'reading_card',
  'review_section',
  'experiment_planner',
  'sql_analyst',
  'citation_organizer',
  'idea_explorer',
  'benchmark',
  'leader',
  'viewer',
  'writer',
  'drawer',
  'progress',
] as const;
export type AgentType = (typeof AGENT_TYPES)[number];

export const AGENT_RUN_STATUSES = [
  'queued',
  'running',
  'completed',
  'failed',
  'cancelled',
] as const;
export type AgentRunStatus = (typeof AGENT_RUN_STATUSES)[number];

export type ToolCallStatus = 'pending' | 'succeeded' | 'failed';
