import { apiRequest } from './client';

export interface LatexProject {
  id: string;
  project_id: string;
  name: string;
  main_file_path: string;
  created_at: string;
}

export interface DocFileSummary {
  id: string;
  path: string;
  version: number;
}

export interface DocFile {
  id: string;
  path: string;
  content: string;
  version: number;
  updated_at: string;
}

export interface CompileJob {
  id: string;
  latex_project_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  engine: string;
  log: string | null;
  preview: string | null;
  error_summary: string | null;
  created_at: string;
  finished_at: string | null;
}

const lp = (p: string) => `/projects/${p}/latex-projects`;

export const listLatexProjects = (p: string): Promise<LatexProject[]> => apiRequest(lp(p));
export const createLatexProject = (p: string, name: string): Promise<LatexProject> =>
  apiRequest(lp(p), { method: 'POST', body: { name } });
export const listFiles = (p: string, id: string): Promise<DocFileSummary[]> =>
  apiRequest(`${lp(p)}/${id}/files`);
export const getFile = (p: string, id: string, path: string): Promise<DocFile> =>
  apiRequest(`${lp(p)}/${id}/files/content?path=${encodeURIComponent(path)}`);
export const saveFile = (p: string, id: string, path: string, content: string): Promise<DocFile> =>
  apiRequest(`${lp(p)}/${id}/files`, { method: 'PUT', body: { path, content } });
export const compile = (p: string, id: string): Promise<CompileJob> =>
  apiRequest(`${lp(p)}/${id}/compile`, { method: 'POST' });
