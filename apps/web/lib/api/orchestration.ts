import { apiRequest } from './client';

export type MissionTaskStatus =
  | 'draft'
  | 'ready'
  | 'leased'
  | 'running'
  | 'artifact_ready'
  | 'waiting_approval'
  | 'completed'
  | 'retryable_failed'
  | 'terminal_failed'
  | 'cancelled';

export interface MissionTask {
  id: string;
  project_id: string;
  mission_id: string;
  mission_step_id: string | null;
  parent_task_id: string | null;
  task_key: string;
  title: string;
  role: string;
  agent_type: string | null;
  status: MissionTaskStatus;
  priority: number;
  attempt: number;
  max_attempts: number;
  idempotency_key: string;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown>;
  acceptance_json: string[];
  permissions_json: string[];
  budget_json: Record<string, unknown>;
  agent_run_id: string | null;
  available_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  last_error_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface TaskDependency {
  id: string;
  task_id: string;
  depends_on_task_id: string;
  required_artifact_schema: string | null;
}

export interface TaskArtifact {
  id: string;
  mission_id: string;
  task_id: string;
  schema_name: string;
  schema_version: number;
  content_hash: string;
  uri: string | null;
  metadata_json: Record<string, unknown>;
  producer_run_id: string | null;
  visibility: string;
  created_at: string;
}

export interface ApprovalGate {
  id: string;
  mission_id: string;
  task_id: string;
  gate_kind: string;
  status: 'pending' | 'approved' | 'rejected';
  request_json: Record<string, unknown>;
  decision_json: Record<string, unknown>;
  requested_by: string;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface TaskEvent {
  id: string;
  task_id: string;
  seq: number;
  event_type: string;
  payload_json: Record<string, unknown>;
  actor_id: string | null;
  message: string | null;
  created_at: string;
}

export interface OrchestrationGraph {
  mission_id: string;
  tasks: MissionTask[];
  dependencies: TaskDependency[];
  artifacts: TaskArtifact[];
  gates: ApprovalGate[];
  events: TaskEvent[];
  counts: Record<string, number>;
}

export type ResearchLoopStatus = 'active' | 'paused' | 'completed' | 'cancelled';
export type ResearchIterationStatus = 'proposed' | 'running' | 'kept' | 'discarded' | 'crashed';

export interface ResearchLoopIteration {
  id: string;
  loop_id: string;
  project_id: string;
  mission_id: string;
  task_id: string;
  iteration_number: number;
  status: ResearchIterationStatus;
  hypothesis: string;
  component: string;
  expected_effect: string;
  changed_paths_json: string[];
  patch_id: string | null;
  agent_run_id: string | null;
  experiment_run_id: string | null;
  code_commit_sha: string | null;
  metric_value: number | null;
  improvement: number | null;
  complexity_delta: number | null;
  critic_score: number | null;
  rule_checks_json: Record<string, boolean>;
  decision_json: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface ResearchLoop {
  id: string;
  project_id: string;
  mission_id: string;
  task_id: string;
  name: string;
  status: ResearchLoopStatus;
  metric_name: string;
  metric_direction: 'min' | 'max';
  metric_aggregation: 'final' | 'best';
  baseline_run_id: string;
  best_run_id: string;
  baseline_metric_value: number;
  best_metric_value: number;
  fixed_budget_seconds: number;
  max_iterations: number;
  patience: number;
  min_delta: number;
  max_complexity_delta: number;
  critic_threshold: number;
  current_iteration: number;
  no_improvement_count: number;
  editable_scope_json: string[];
  protected_scope_json: string[];
  stop_reason: string | null;
  created_at: string;
  updated_at: string;
  iterations: ResearchLoopIteration[];
}

const base = (projectId: string) => `/projects/${projectId}/orchestration`;

export function getOrchestrationGraph(
  projectId: string,
  missionId: string,
): Promise<OrchestrationGraph> {
  return apiRequest(`${base(projectId)}/missions/${missionId}`);
}

export function bootstrapOrchestrationGraph(
  projectId: string,
  missionId: string,
): Promise<OrchestrationGraph> {
  return apiRequest(`${base(projectId)}/missions/${missionId}/bootstrap`, { method: 'POST' });
}

export function tickOrchestration(
  projectId: string,
  missionId: string,
): Promise<{
  graph: OrchestrationGraph;
  promoted: number;
  reclaimed: number;
  reconciled: number;
}> {
  return apiRequest(`${base(projectId)}/missions/${missionId}/tick`, { method: 'POST' });
}

export function decideApprovalGate(
  projectId: string,
  gateId: string,
  decision: 'approve' | 'reject',
  note = '',
): Promise<MissionTask> {
  return apiRequest(`${base(projectId)}/gates/${gateId}/decision`, {
    method: 'POST',
    body: { decision, note },
  });
}

export function dispatchMissionTask(
  projectId: string,
  taskId: string,
  message: string,
  context: Record<string, unknown>,
): Promise<{ task_id: string; agent_run_id: string; status: string; stream: string }> {
  return apiRequest(`${base(projectId)}/tasks/${taskId}/dispatch`, {
    method: 'POST',
    body: { message, context },
  });
}

export function listResearchLoops(
  projectId: string,
  missionId: string,
): Promise<ResearchLoop[]> {
  return apiRequest(`${base(projectId)}/missions/${missionId}/research-loops`);
}

export function createResearchLoop(
  projectId: string,
  missionId: string,
  body: {
    name: string;
    metric_name: string;
    metric_direction: 'min' | 'max';
    metric_aggregation: 'final' | 'best';
    baseline_run_id: string;
    fixed_budget_seconds: number;
    max_iterations: number;
    patience: number;
    min_delta: number;
    max_complexity_delta: number;
    critic_threshold: number;
    editable_scopes: string[];
    protected_scopes: string[];
  },
): Promise<ResearchLoop> {
  return apiRequest(`${base(projectId)}/missions/${missionId}/research-loops`, {
    method: 'POST',
    body,
  });
}

export function createResearchIteration(
  projectId: string,
  loopId: string,
  body: {
    hypothesis: string;
    component: string;
    expected_effect: string;
    changed_paths: string[];
  },
): Promise<ResearchLoop> {
  return apiRequest(`${base(projectId)}/research-loops/${loopId}/iterations`, {
    method: 'POST',
    body,
  });
}

export function evaluateResearchIteration(
  projectId: string,
  iterationId: string,
  body: {
    experiment_run_id: string;
    patch_id?: string;
    complexity_delta: number;
    critic_score: number;
    rule_checks: Record<string, boolean>;
  },
): Promise<ResearchLoop> {
  return apiRequest(`${base(projectId)}/research-iterations/${iterationId}/evaluate`, {
    method: 'POST',
    body,
  });
}

export function controlResearchLoop(
  projectId: string,
  loopId: string,
  action: 'pause' | 'resume' | 'finalize' | 'cancel',
  reason = '',
): Promise<ResearchLoop> {
  return apiRequest(`${base(projectId)}/research-loops/${loopId}/control`, {
    method: 'POST',
    body: { action, reason },
  });
}
