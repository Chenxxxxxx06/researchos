import { apiRequest } from './client';

export interface ZoteroConnection {
  id: string;
  library_type: 'user' | 'group';
  library_id: string;
  api_key_masked: string;
  enabled: boolean;
  include_collections: string[];
  last_library_version: number;
  last_synced_at: string | null;
  last_error: string | null;
}

export interface SaveZoteroConnection {
  library_type: 'user' | 'group';
  library_id: string;
  api_key: string;
  enabled: boolean;
  include_collections?: string[];
}

export interface ZoteroConnectionTest {
  ok: boolean;
  message: string;
  username: string | null;
  user_id: string | null;
  library_access: boolean;
  latency_ms: number;
}

export interface ZoteroSyncResult {
  created: number;
  updated: number;
  linked: number;
  skipped: number;
  library_version: number;
  last_synced_at: string;
}

export function getZoteroConnection(projectId: string): Promise<ZoteroConnection | null> {
  return apiRequest(`/projects/${projectId}/integrations/zotero`);
}

export function saveZoteroConnection(
  projectId: string,
  input: SaveZoteroConnection,
): Promise<ZoteroConnection> {
  return apiRequest(`/projects/${projectId}/integrations/zotero`, {
    method: 'PUT',
    body: input,
  });
}

export function testZoteroConnection(projectId: string): Promise<ZoteroConnectionTest> {
  return apiRequest(`/projects/${projectId}/integrations/zotero/test`, {
    method: 'POST',
  });
}

export function syncZoteroLibrary(projectId: string): Promise<ZoteroSyncResult> {
  return apiRequest(`/projects/${projectId}/integrations/zotero/sync`, {
    method: 'POST',
  });
}
