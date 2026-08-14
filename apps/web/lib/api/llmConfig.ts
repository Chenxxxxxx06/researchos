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

export interface LLMConfigInput {
  name: string;
  provider_type?: string;
  base_url?: string;
  model?: string;
  api_key?: string;
  is_active?: boolean;
  description?: string;
}

export interface LLMConnectionTest {
  ok: boolean;
  provider_type: string;
  model: string;
  latency_ms: number;
  message: string;
  sample: string | null;
  input_tokens: number;
  output_tokens: number;
}

export function listLLMConfigs(projectId: string): Promise<LLMConfig[]> {
  return apiRequest(`/projects/${projectId}/settings/llm`);
}

export function saveLLMConfig(projectId: string, input: LLMConfigInput): Promise<LLMConfig> {
  return apiRequest(`/projects/${projectId}/settings/llm`, { method: 'POST', body: input });
}

export function updateLLMConfig(
  projectId: string,
  configId: string,
  input: LLMConfigInput,
): Promise<LLMConfig> {
  return apiRequest(`/projects/${projectId}/settings/llm/${configId}`, {
    method: 'PATCH',
    body: input,
  });
}

export function deleteLLMConfig(projectId: string, configId: string): Promise<void> {
  return apiRequest(`/projects/${projectId}/settings/llm/${configId}`, { method: 'DELETE' });
}

export function testLLMConfig(
  projectId: string,
  configId: string,
): Promise<LLMConnectionTest> {
  return apiRequest(`/projects/${projectId}/settings/llm/${configId}/test`, {
    method: 'POST',
  });
}
