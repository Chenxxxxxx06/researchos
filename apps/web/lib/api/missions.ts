import { apiRequest } from './client';
import type { Page } from './projects';

export type MissionStatus = 'draft' | 'active' | 'paused' | 'completed' | 'archived';
export type MissionStepKind = 'scope' | 'literature' | 'reading' | 'review' | 'experiment_plan';
export type MissionStepStatus = 'locked' | 'ready' | 'in_progress' | 'needs_review' | 'completed';

export interface MissionStep {
  id: string;
  mission_id: string;
  project_id: string;
  step_kind: MissionStepKind;
  position: number;
  status: MissionStepStatus;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown>;
  version: number;
  started_at: string | null;
  completed_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  updated_at: string;
}

export interface MissionSummary {
  id: string;
  project_id: string;
  topic: string;
  objective: string;
  field: string | null;
  status: MissionStatus;
  current_step: MissionStepKind;
  scope_json: Record<string, unknown>;
  progress: number;
  version: number;
  last_activity_at: string;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface MissionDetail extends MissionSummary {
  steps: MissionStep[];
}

export interface MissionEvent {
  id: string;
  mission_id: string;
  project_id: string;
  event_type: string;
  summary: string;
  step_kind: MissionStepKind | null;
  payload_json: Record<string, unknown>;
  actor_id: string | null;
  created_at: string;
}

export function listMissions(projectId: string, status?: MissionStatus): Promise<Page<MissionSummary>> {
  const query = new URLSearchParams({ limit: '100' });
  if (status) query.set('status', status);
  return apiRequest<Page<MissionSummary>>(`/projects/${projectId}/missions?${query}`);
}

export function createMission(
  projectId: string,
  input: {
    topic: string;
    objective?: string;
    field?: string;
    scope?: Record<string, unknown>;
  },
): Promise<MissionDetail> {
  return apiRequest<MissionDetail>(`/projects/${projectId}/missions`, {
    method: 'POST',
    body: input,
  });
}

export function getMission(projectId: string, missionId: string): Promise<MissionDetail> {
  return apiRequest<MissionDetail>(`/projects/${projectId}/missions/${missionId}`);
}

export function updateMission(
  projectId: string,
  missionId: string,
  input: {
    expected_version: number;
    topic?: string;
    objective?: string;
    field?: string;
    scope?: Record<string, unknown>;
    status?: MissionStatus;
  },
): Promise<MissionDetail> {
  return apiRequest<MissionDetail>(`/projects/${projectId}/missions/${missionId}`, {
    method: 'PATCH',
    body: input,
  });
}

export function updateMissionStep(
  projectId: string,
  missionId: string,
  step: MissionStepKind,
  input: {
    expected_version: number;
    input?: Record<string, unknown>;
    output?: Record<string, unknown>;
    status?: MissionStepStatus;
  },
): Promise<MissionDetail> {
  return apiRequest<MissionDetail>(
    `/projects/${projectId}/missions/${missionId}/steps/${step}`,
    { method: 'PUT', body: input },
  );
}

export function approveMissionStep(
  projectId: string,
  missionId: string,
  step: MissionStepKind,
  input: { expected_version: number; note?: string },
): Promise<MissionDetail> {
  return apiRequest<MissionDetail>(
    `/projects/${projectId}/missions/${missionId}/steps/${step}/approve`,
    { method: 'POST', body: input },
  );
}

export function getMissionTimeline(
  projectId: string,
  missionId: string,
): Promise<Page<MissionEvent>> {
  return apiRequest<Page<MissionEvent>>(
    `/projects/${projectId}/missions/${missionId}/timeline?limit=100`,
  );
}
