/**
 * ResearchOS WebSocket event contracts.
 *
 * The envelope shape and event-type vocabulary mirror the backend
 * (apps/api/researchos/websocket/envelopes.py) and its per-domain producers:
 * agents/runtime/{events,tools}.py (agent.*), research/ingest.py
 * (paper.ingest.*), experiments/{service,ingest}.py (experiment.*),
 * documents/service.py (latex.compile.*), and
 * figures/{figure_service,render_job,events}.py (figure.render.*,
 * anchor.values.updated).
 *
 * AGENT_EVENTS must stay equal to AGENT_EVENT_TYPES in envelopes.py —
 * apps/api/tests/test_ws_contract.py asserts that set equality.
 */

import type { AgentType } from './agents';
import type { CompileStatus } from './documents';
import type { ExperimentRunStatus } from './experiments';

/** Domain event type identifiers grouped by producer. */
export const AGENT_EVENTS = [
  'agent.run.started',
  'agent.run.token',
  'agent.run.tool_call.started',
  'agent.run.tool_call.completed',
  'agent.run.completed',
  'agent.run.failed',
  'agent.run.cancelled',
] as const;

export const RESEARCH_EVENTS = [
  'paper.ingest.started',
  'paper.ingest.completed',
  'paper.ingest.failed',
] as const;

export const EXPERIMENT_EVENTS = [
  'experiment.run.queued',
  'experiment.run.started',
  'experiment.run.completed',
  'experiment.run.failed',
  'experiment.metric.recorded',
  'experiment.log.appended',
] as const;

export const LATEX_EVENTS = ['latex.compile.completed', 'latex.compile.failed'] as const;

export const FIGURE_EVENTS = [
  'figure.render.queued',
  'figure.render.started',
  'figure.render.completed',
  'figure.render.failed',
] as const;

export const ANCHOR_EVENTS = ['anchor.values.updated'] as const;

export const EVENT_TYPES = [
  ...AGENT_EVENTS,
  ...RESEARCH_EVENTS,
  ...EXPERIMENT_EVENTS,
  ...LATEX_EVENTS,
  ...FIGURE_EVENTS,
  ...ANCHOR_EVENTS,
] as const;

export type AgentEventType = (typeof AGENT_EVENTS)[number];
export type EventType = (typeof EVENT_TYPES)[number];

export type ResourceType =
  | 'agent_run'
  | 'experiment_run'
  | 'latex_compile'
  | 'runtime_command'
  | 'skill_installation'
  | 'project'
  | 'paper'
  | 'figure';

/** Canonical WebSocket event envelope. */
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

// --- Client heartbeat --------------------------------------------------------
// The gateway reads client frames, answers pings, and ignores anything else.

export interface PingMessage {
  type: 'ping';
  ts: number;
}

export interface PongMessage {
  type: 'pong';
  /** Echo of the ping's ts (null when the ping carried none). */
  ts: number | null;
}

// --- Agent event payloads ----------------------------------------------------

export interface SkillGrantRef {
  slug: string;
  version: string;
}

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
  /** Skills injected into this run (always present, possibly empty). */
  skills: SkillGrantRef[];
}

export interface AgentRunTokenPayload {
  delta: string;
  /** Monotone per-run delta sequence for client-side ordering. */
  seq: number;
}

export interface AgentRunToolCallStartedPayload {
  seq: number;
  tool_name: string;
  arguments: Record<string, unknown>;
  /** "agent" or the granting skill slug. */
  granted_by: string;
}

export interface AgentRunToolCallCompletedPayload {
  seq: number;
  tool_name: string;
  status: 'succeeded' | 'failed';
  result_summary: string | null;
}

export interface AgentRunCompletedPayload {
  output: string;
  citations: PaperCitation[];
  usage: TokenUsage;
}

export const AGENT_RUN_FAILURE_CODES = [
  'timeout',
  'structured_output_parse_error',
  'llm_error',
  'config_error',
  'agent_error',
  'tool_denied',
] as const;
export type AgentRunFailureCode = (typeof AGENT_RUN_FAILURE_CODES)[number];

export interface AgentRunFailedPayload {
  error: string;
  /** Always present; usually one of AGENT_RUN_FAILURE_CODES. */
  code: string;
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
}

// --- Research (paper ingest) payloads ----------------------------------------

export interface PaperIngestStartedPayload {
  paper_id: string;
}

export interface PaperIngestCompletedPayload {
  paper_id: string;
  status: 'succeeded' | 'abstract_only';
  section_count: number;
}

export interface PaperIngestFailedPayload {
  paper_id: string;
  error: string;
}

// --- Experiment payloads -----------------------------------------------------

/** Payload of experiment.run.{queued,started,completed,failed}. */
export interface ExperimentRunStatusPayload {
  run_id: string;
  experiment_id: string;
  status: ExperimentRunStatus;
}

export interface ExperimentMetricRecordedPayload {
  run_id: string;
  count: number;
  names: string[];
}

export interface ExperimentLogAppendedPayload {
  run_id: string;
  count: number;
  last_seq: number;
}

// --- LaTeX compile payloads --------------------------------------------------

/** Payload of latex.compile.{completed,failed}. */
export interface LatexCompileFinishedPayload {
  job_id: string;
  status: CompileStatus;
  engine: string;
  diagnostics_count: number;
  error_summary: string | null;
}

// --- Figure / anchor payloads ------------------------------------------------

/** Payload of figure.render.{queued,started}. */
export interface FigureRenderLifecyclePayload {
  figure_id: string;
  name: string;
}

export interface FigureRenderCompletedPayload extends FigureRenderLifecyclePayload {
  formats: string[];
  style_slug: string;
  style_version: string;
  source_run_ids: string[];
}

export interface FigureRenderFailedPayload extends FigureRenderLifecyclePayload {
  error: string;
}

export interface AnchorValuesUpdatedPayload {
  updated_count: number;
  stale_count: number;
  anchor_ids: string[];
}

/** Map every event type to its payload shape. */
export interface EventPayloadMap extends AgentEventPayloadMap {
  'paper.ingest.started': PaperIngestStartedPayload;
  'paper.ingest.completed': PaperIngestCompletedPayload;
  'paper.ingest.failed': PaperIngestFailedPayload;
  'experiment.run.queued': ExperimentRunStatusPayload;
  'experiment.run.started': ExperimentRunStatusPayload;
  'experiment.run.completed': ExperimentRunStatusPayload;
  'experiment.run.failed': ExperimentRunStatusPayload;
  'experiment.metric.recorded': ExperimentMetricRecordedPayload;
  'experiment.log.appended': ExperimentLogAppendedPayload;
  'latex.compile.completed': LatexCompileFinishedPayload;
  'latex.compile.failed': LatexCompileFinishedPayload;
  'figure.render.queued': FigureRenderLifecyclePayload;
  'figure.render.started': FigureRenderLifecyclePayload;
  'figure.render.completed': FigureRenderCompletedPayload;
  'figure.render.failed': FigureRenderFailedPayload;
  'anchor.values.updated': AnchorValuesUpdatedPayload;
}
