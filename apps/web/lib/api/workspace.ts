import { apiRequest } from './client';

export interface TreeNode {
  name: string;
  path: string;
  type: 'file' | 'dir';
  children?: TreeNode[];
}

export interface TreeResponse {
  root: string;
  nodes: TreeNode[];
}

export interface FileContent {
  path: string;
  binary: boolean;
  too_large: boolean;
  size: number;
  sha: string | null;
  content: string | null;
}

export function getTree(projectId: string): Promise<TreeResponse> {
  return apiRequest(`/projects/${projectId}/workspace/tree`);
}

export function getFile(projectId: string, path: string): Promise<FileContent> {
  return apiRequest(`/projects/${projectId}/workspace/files?path=${encodeURIComponent(path)}`);
}
