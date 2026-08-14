import { describe, expect, it } from 'vitest';

import type { LLMConfig } from '@/lib/api/llmConfig';

import { firstEnabledConfigId, reconcileSelectedConfigId } from './modelSelection';

function config(id: string, isActive: boolean): LLMConfig {
  return {
    id,
    name: id,
    provider_type: 'openai_compatible',
    base_url: 'https://example.test/v1',
    model: `model-${id}`,
    api_key_masked: '***test',
    is_active: isActive,
    description: null,
  };
}

const inactive = config('inactive', false);
const newestEnabled = config('newest', true);
const olderEnabled = config('older', true);

describe('Research Copilot model selection', () => {
  it('selects the first enabled config from newest-first results', () => {
    expect(firstEnabledConfigId([inactive, newestEnabled, olderEnabled])).toBe('newest');
  });

  it('keeps a current selection while it remains enabled', () => {
    expect(reconcileSelectedConfigId([newestEnabled, olderEnabled], 'older')).toBe('older');
  });

  it('falls back when the selected config is removed or disabled', () => {
    expect(reconcileSelectedConfigId([newestEnabled, inactive], 'inactive')).toBe('newest');
  });

  it('returns an empty selection when no config is enabled', () => {
    expect(reconcileSelectedConfigId([inactive], 'inactive')).toBe('');
  });
});
