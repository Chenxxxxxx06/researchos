import { apiRequest } from './client';
import type { FileContent, TerminalRunResult, TreeResponse } from './workspace';

export interface SSHProfile {
  id: string;
  project_id: string;
  name: string;
  host: string;
  port: number;
  username: string;
  auth_type: 'password' | 'ssh_key';
  credential_masked: string;
  default_workdir: string;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SSHProfileInput {
  id?: string;
  name: string;
  host: string;
  port: number;
  username: string;
  auth_type: 'password' | 'ssh_key';
  secret?: string;
  key_passphrase?: string;
  known_hosts: string;
  default_workdir: string;
}

const base = (projectId: string) => `/projects/${projectId}/workspace/ssh`;

export const listSSHProfiles = (projectId: string): Promise<SSHProfile[]> =>
  apiRequest(`${base(projectId)}/profiles`);

export const saveSSHProfile = (projectId: string, input: SSHProfileInput): Promise<SSHProfile> =>
  apiRequest(`${base(projectId)}/profiles`, { method: 'PUT', body: input });

export const deleteSSHProfile = (projectId: string, profileId: string): Promise<void> =>
  apiRequest(`${base(projectId)}/profiles/${profileId}`, { method: 'DELETE' });

export const testSSHProfile = (projectId: string, profileId: string): Promise<{ ok: boolean; message: string; latency_ms: number; server_version: string | null }> =>
  apiRequest(`${base(projectId)}/profiles/${profileId}/test`, { method: 'POST' });

export const getSSHTree = (projectId: string, profileId: string): Promise<TreeResponse> =>
  apiRequest(`${base(projectId)}/profiles/${profileId}/tree`);

export const getSSHFile = (projectId: string, profileId: string, path: string): Promise<FileContent> =>
  apiRequest(`${base(projectId)}/profiles/${profileId}/files?path=${encodeURIComponent(path)}`);

export const saveSSHFile = (projectId: string, profileId: string, input: { path: string; content: string; base_sha: string | null }): Promise<FileContent> =>
  apiRequest(`${base(projectId)}/profiles/${profileId}/files`, { method: 'PUT', body: input });

export const runSSHCommand = (projectId: string, profileId: string, input: { argv: string[]; cwd?: string; timeout_seconds?: number }): Promise<TerminalRunResult> =>
  apiRequest(`${base(projectId)}/profiles/${profileId}/terminal/run`, {
    method: 'POST',
    body: { argv: input.argv, cwd: input.cwd ?? '.', timeout_seconds: input.timeout_seconds ?? 30 },
  });
