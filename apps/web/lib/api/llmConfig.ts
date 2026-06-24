import { apiRequest } from './client';

export interface LLMConfig {
  id: string;
  name: string;
  provider_type: string;
  base_url: string;
  model: string;
  api_key_masked: string;
  is_active: boolean;
  description: string | null;
}

export interface SaveLLMConfigInput {
  name: string;
  provider_type?: string;
  base_url?: string;
  model?: string;
  api_key?: string;
  is_active?: boolean;
  description?: string;
}

export function listLLMConfigs(projectId: string): Promise<LLMConfig[]> {
  return apiRequest(`/projects/${projectId}/settings/llm`);
}

export function saveLLMConfig(projectId: string, input: SaveLLMConfigInput): Promise<LLMConfig> {
  return apiRequest(`/projects/${projectId}/settings/llm`, { method: 'POST', body: input });
}

export function deleteLLMConfig(projectId: string, configId: string): Promise<void> {
  return apiRequest(`/projects/${projectId}/settings/llm/${configId}`, { method: 'DELETE' });
}
