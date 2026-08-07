import type { CreateAgentRunResponse } from './agents';
import { apiRequest } from './client';

export type VariableRole = 'independent' | 'dependent' | 'control' | 'confounder';

export interface PlanVariable {
  name: string;
  role: VariableRole;
  operational_definition: string;
  levels_or_measurement: string;
}

export interface PlanBaseline {
  name: string;
  rationale: string;
  source_paper_id: string | null;
  evidence_section_id: string | null;
  evidence_quote: string;
  evidence_status: 'grounded' | 'needs_evidence';
}

export interface PlanDataset {
  name: string;
  split: string;
  preprocessing: string;
  license_or_access: string;
}

export interface PlanMetric {
  name: string;
  direction: 'min' | 'max';
  primary: boolean;
  unit: string;
}

export interface PlanMatrixRow {
  name: string;
  factors: Record<string, unknown>;
  repetitions: number;
  seed_policy: string;
  compute_budget: string;
}

export interface PlanRisk {
  risk: string;
  mitigation: string;
  severity: 'low' | 'medium' | 'high';
}

export interface ExperimentPlan {
  id: string;
  project_id: string;
  mission_id: string;
  title: string;
  research_gap: string;
  hypothesis: string;
  variables_json: PlanVariable[];
  baselines_json: PlanBaseline[];
  datasets_json: PlanDataset[];
  metrics_json: PlanMetric[];
  matrix_json: PlanMatrixRow[];
  decision_rules_json: string[];
  stop_conditions_json: string[];
  risks_json: PlanRisk[];
  reproducibility_json: string[];
  status: 'draft' | 'needs_review' | 'approved' | 'published';
  version: number;
  generated_by_run_id: string | null;
  published_experiment_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExperimentPlanInput {
  expected_version?: number;
  title: string;
  research_gap: string;
  hypothesis: string;
  variables: PlanVariable[];
  baselines: PlanBaseline[];
  datasets: PlanDataset[];
  metrics: PlanMetric[];
  matrix: PlanMatrixRow[];
  decision_rules: string[];
  stop_conditions: string[];
  risks: PlanRisk[];
  reproducibility: string[];
  status: 'draft' | 'needs_review' | 'approved';
}

export interface ExperimentPlanVersion {
  id: string;
  plan_id: string;
  version: number;
  snapshot_json: Record<string, unknown>;
  source_type: string;
  source_run_id: string | null;
  created_by: string;
  created_at: string;
}

const path = (projectId: string, missionId: string) =>
  `/projects/${projectId}/missions/${missionId}/experiment-plan`;

export const getExperimentPlan = (projectId: string, missionId: string) =>
  apiRequest<ExperimentPlan>(path(projectId, missionId));

export const saveExperimentPlan = (
  projectId: string,
  missionId: string,
  input: ExperimentPlanInput,
) => apiRequest<ExperimentPlan>(path(projectId, missionId), { method: 'PUT', body: input });

export const generateExperimentPlan = (
  projectId: string,
  missionId: string,
  expectedVersion: number,
  regenerate: boolean,
) =>
  apiRequest<CreateAgentRunResponse>(`${path(projectId, missionId)}/generate`, {
    method: 'POST',
    body: { expected_version: expectedVersion, regenerate },
  });

export const listExperimentPlanVersions = (projectId: string, missionId: string) =>
  apiRequest<ExperimentPlanVersion[]>(`${path(projectId, missionId)}/versions`);

export const publishExperimentPlan = (projectId: string, missionId: string) =>
  apiRequest<{ plan: ExperimentPlan; experiment_id: string }>(
    `${path(projectId, missionId)}/publish`,
    { method: 'POST' },
  );
