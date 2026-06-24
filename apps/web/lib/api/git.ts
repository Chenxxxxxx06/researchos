import { apiRequest } from './client';

export interface GitFileStatus {
  path: string;
  state: 'modified' | 'added' | 'deleted' | 'untracked' | 'renamed';
}

export interface GitStatus {
  provider: string;
  branch: string;
  clean: boolean;
  ahead: number;
  behind: number;
  files: GitFileStatus[];
}

export function getGitStatus(projectId: string): Promise<GitStatus> {
  return apiRequest(`/projects/${projectId}/git/status`);
}
