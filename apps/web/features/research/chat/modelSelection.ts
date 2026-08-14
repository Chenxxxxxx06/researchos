import type { LLMConfig } from '@/lib/api/llmConfig';

export function firstEnabledConfigId(configs: LLMConfig[]): string {
  return configs.find((config) => config.is_active)?.id ?? '';
}

export function reconcileSelectedConfigId(
  configs: LLMConfig[],
  selectedId: string,
): string {
  const selected = configs.find((config) => config.id === selectedId);
  return selected?.is_active ? selectedId : firstEnabledConfigId(configs);
}
