import { apiRequest } from './client';

export type ProjectStatus = 'active' | 'archived';

export interface Project {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  field: string | null;
  status: ProjectStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export function listProjects(organizationId: string): Promise<Page<Project>> {
  return apiRequest<Page<Project>>(
    `/projects?organization_id=${encodeURIComponent(organizationId)}`,
  );
}

export function getProject(projectId: string): Promise<Project> {
  return apiRequest<Project>(`/projects/${projectId}`);
}

export function createProject(input: {
  organization_id: string;
  name: string;
  description?: string;
  field?: string;
}): Promise<Project> {
  return apiRequest<Project>('/projects', { method: 'POST', body: input });
}
