import { apiRequest } from './client';

export interface SkillCatalogItem {
  slug: string;
  name: string;
  description: string;
  author: string;
  category: string;
  visibility: 'first_party' | 'custom';
  modules: string[];
  installed: boolean;
  enabled: boolean;
}

export interface SkillDetail {
  slug: string;
  name: string;
  description: string;
  author: string;
  category: string;
  visibility: 'first_party' | 'custom';
  version: string;
  modules: string[];
  prompt_template: string;
  workflow: string[];
  tool_permissions: string[];
  config_schema: Record<string, unknown>;
  installed: boolean;
  enabled: boolean;
}

export interface InstalledSkill {
  slug: string;
  name: string;
  version: string;
  enabled: boolean;
}

export interface CustomSkillInput {
  slug: string;
  name: string;
  version: string;
  description: string;
  category: string;
  modules: string[];
  prompt_template: string;
  workflow: string[];
  tool_permissions: string[];
  config_schema: Record<string, unknown>;
}

const base = (p: string) => `/projects/${p}/skills`;

export const listCatalog = (p: string): Promise<SkillCatalogItem[]> => apiRequest(`${base(p)}/catalog`);
export const listInstalled = (p: string): Promise<InstalledSkill[]> => apiRequest(`${base(p)}/installed`);
export const getSkill = (p: string, slug: string): Promise<SkillDetail> => apiRequest(`${base(p)}/${slug}`);
export const allowedTools = (p: string): Promise<string[]> => apiRequest(`${base(p)}/allowed-tools`);
export const installSkill = (p: string, slug: string): Promise<void> =>
  apiRequest(`${base(p)}/${slug}/install`, { method: 'POST' });
export const toggleSkill = (p: string, slug: string, enabled: boolean): Promise<void> =>
  apiRequest(`${base(p)}/${slug}/toggle`, { method: 'POST', body: { enabled } });
export const validateSkill = (
  p: string,
  body: CustomSkillInput,
): Promise<{ valid: boolean; errors: string[] }> =>
  apiRequest(`${base(p)}/validate`, { method: 'POST', body });
export const createCustomSkill = (p: string, body: CustomSkillInput): Promise<SkillDetail> =>
  apiRequest(`${base(p)}/custom`, { method: 'POST', body });
