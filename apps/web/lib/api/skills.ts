import { apiRequest } from './client';

export interface InstalledSkill {
  slug: string;
  name: string;
  version: string;
  enabled: boolean;
}

export function listInstalledSkills(projectId: string): Promise<InstalledSkill[]> {
  return apiRequest(`/projects/${projectId}/skills/installed`);
}

export function installSkill(projectId: string, slug: string): Promise<void> {
  return apiRequest(`/projects/${projectId}/skills/${encodeURIComponent(slug)}/install`, {
    method: 'POST',
  });
}
