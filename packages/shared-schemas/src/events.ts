/**
 * ResearchOS WebSocket event contracts.
 *
 * These mirror docs/WEBSOCKET.md. The envelope and the event-type union are the
 * canonical contract shared between the backend gateway (later phase) and the
 * frontend WebSocket client. Per-event payload types are added as each feature
 * lands; Phase 0 only fixes the envelope and the event-type vocabulary.
 */

/** Domain event type identifiers grouped by source. */
export const AGENT_EVENTS = [
  'agent.run.started',
  'agent.run.token',
  'agent.run.tool_call.started',
  'agent.run.tool_call.completed',
  'agent.run.approval_required',
  'agent.run.completed',
  'agent.run.failed',
  'agent.run.cancelled',
] as const;

export const EXPERIMENT_EVENTS = [
  'experiment.run.queued',
  'experiment.run.started',
  'experiment.metric.recorded',
  'experiment.log.appended',
  'experiment.artifact.created',
  'experiment.run.completed',
  'experiment.run.failed',
] as const;

export const RUNTIME_EVENTS = [
  'runtime.ssh.connected',
  'runtime.ssh.disconnected',
  'runtime.command.started',
  'runtime.command.output',
  'runtime.command.completed',
  'runtime.command.failed',
] as const;

export const LATEX_EVENTS = [
  'latex.compile.queued',
  'latex.compile.started',
  'latex.compile.log',
  'latex.compile.completed',
  'latex.compile.failed',
] as const;

export const SKILL_EVENTS = [
  'skill.install.started',
  'skill.install.validated',
  'skill.install.completed',
  'skill.install.failed',
] as const;

export const EVENT_TYPES = [
  ...AGENT_EVENTS,
  ...EXPERIMENT_EVENTS,
  ...RUNTIME_EVENTS,
  ...LATEX_EVENTS,
  ...SKILL_EVENTS,
] as const;

export type EventType = (typeof EVENT_TYPES)[number];

export type ResourceType =
  | 'agent_run'
  | 'experiment_run'
  | 'latex_compile'
  | 'runtime_command'
  | 'skill_installation'
  | 'project';

/** Canonical WebSocket event envelope (see docs/WEBSOCKET.md §3). */
export interface EventEnvelope<TPayload = Record<string, unknown>> {
  event_id: string;
  event_type: EventType;
  project_id: string;
  resource_type: ResourceType;
  resource_id: string;
  /** ISO-8601 timestamp. */
  timestamp: string;
  payload: TPayload;
}

export function isEventType(value: string): value is EventType {
  return (EVENT_TYPES as readonly string[]).includes(value);
}

// --- Agent event payloads ----------------------------------------------------
// Typed payloads for the Phase 2 agent run streaming events. Kept in sync with
// the backend Pydantic envelopes (researchos/websocket/envelopes.py).

export type AgentType = 'research' | 'critic';
export type ToolCallStatus = 'pending' | 'succeeded' | 'failed';

export interface PaperCitation {
  source: string;
  external_id: string;
  title: string;
  url: string;
}

export interface TokenUsage {
  input_tokens?: number;
  output_tokens?: number;
}

export interface AgentRunStartedPayload {
  agent_type: AgentType;
}

export interface AgentRunTokenPayload {
  delta: string;
}

export interface AgentRunToolCallStartedPayload {
  seq: number;
  tool_name: string;
  arguments: Record<string, unknown>;
}

export interface AgentRunToolCallCompletedPayload {
  seq: number;
  tool_name: string;
  status: ToolCallStatus;
  result_summary?: string;
}

export interface AgentRunCompletedPayload {
  output: string;
  citations: PaperCitation[];
  usage: TokenUsage;
}

export interface AgentRunFailedPayload {
  error: string;
}

/** Map each agent event type to its payload shape. */
export interface AgentEventPayloadMap {
  'agent.run.started': AgentRunStartedPayload;
  'agent.run.token': AgentRunTokenPayload;
  'agent.run.tool_call.started': AgentRunToolCallStartedPayload;
  'agent.run.tool_call.completed': AgentRunToolCallCompletedPayload;
  'agent.run.completed': AgentRunCompletedPayload;
  'agent.run.failed': AgentRunFailedPayload;
  'agent.run.cancelled': Record<string, never>;
  'agent.run.approval_required': Record<string, unknown>;
}
