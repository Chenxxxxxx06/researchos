'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  deleteLLMConfig,
  listLLMConfigs,
  saveLLMConfig,
  testLLMConfig,
  type LLMConfig,
  type LLMConnectionTest,
} from '@/lib/api/llmConfig';
import { useI18n } from '@/lib/i18n';
import { useTheme, type ThemePreference } from '@/lib/theme';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LanguageSwitcher } from '@/features/workspace/LanguageSwitcher';
import { ApiError } from '@/lib/api/client';
import { useParams } from 'next/navigation';
import { cn } from '@/lib/utils';

/** Fixed-hex mini mock previews so each tile shows its own palette. */
const TILE_PREVIEW: Record<ThemePreference, { canvas: string; card: string; line: string }> = {
  light: { canvas: '#fafafa', card: '#ffffff', line: '#d4d4d4' },
  dark: { canvas: '#0c0c0e', card: '#18181b', line: '#3f3f46' },
  system: { canvas: '#fafafa', card: '#18181b', line: '#737373' },
};

function AppearanceTile({
  value,
  label,
  selected,
  onSelect,
}: {
  value: ThemePreference;
  label: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const preview = TILE_PREVIEW[value];
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={cn(
        'flex flex-col items-center gap-2 rounded-lg border p-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60',
        selected ? 'border-accent bg-surface-2' : 'border-border hover:border-border-strong',
      )}
    >
      <span
        aria-hidden="true"
        className="flex h-10 w-16 items-center justify-center rounded border"
        style={{ background: preview.canvas, borderColor: preview.line }}
      >
        <span
          className="flex h-6 w-10 flex-col justify-center gap-1 rounded-sm px-1.5"
          style={{ background: preview.card }}
        >
          <span className="h-0.5 w-full rounded" style={{ background: preview.line }} />
          <span className="h-0.5 w-2/3 rounded" style={{ background: preview.line }} />
        </span>
      </span>
      <span className="text-xs font-medium text-text">{label}</span>
    </button>
  );
}

export default function SettingsPage() {
  const { t } = useI18n();
  const { preference, setTheme } = useTheme();
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId!;
  const queryClient = useQueryClient();

  const configs = useQuery<LLMConfig[]>({
    queryKey: ['llm-configs', projectId],
    queryFn: () => listLLMConfigs(projectId),
  });

  const save = useMutation({
    mutationFn: (input: Parameters<typeof saveLLMConfig>[1]) => saveLLMConfig(projectId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['llm-configs', projectId] }),
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteLLMConfig(projectId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['llm-configs', projectId] }),
  });

  const test = useMutation({
    mutationFn: (id: string) => testLLMConfig(projectId, id),
  });

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: 'default',
    provider_type: 'openai_compatible',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o',
    api_key: '',
    description: '',
  });

  const themeOptions: Array<{ value: ThemePreference; label: string }> = [
    { value: 'light', label: t('theme.light') },
    { value: 'dark', label: t('theme.dark') },
    { value: 'system', label: t('theme.system') },
  ];

  return (
    <div className="max-w-3xl space-y-8">
      <h1 className="text-xl font-bold tracking-tight text-text">{t('settings.title')}</h1>

      {/* Appearance */}
      <Card>
        <CardHeader><CardTitle>{t('settings.appearance')}</CardTitle></CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-muted">{t('settings.appearanceHint')}</p>
          <div role="radiogroup" aria-label={t('settings.appearance')} className="flex gap-3">
            {themeOptions.map((option) => (
              <AppearanceTile
                key={option.value}
                value={option.value}
                label={option.label}
                selected={preference === option.value}
                onSelect={() => setTheme(option.value)}
              />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Language */}
      <Card>
        <CardHeader><CardTitle>{t('settings.language')}</CardTitle></CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-muted">{t('settings.languageHint')}</p>
          <LanguageSwitcher />
        </CardContent>
      </Card>

      {/* LLM Provider Configs */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>{t('settings.llmTitle')}</CardTitle>
            <Button size="sm" variant="secondary" onClick={() => {
              setShowForm(true);
              setForm({ name: 'default', provider_type: 'openai_compatible', base_url: 'https://api.openai.com/v1', model: 'gpt-4o', api_key: '', description: '' });
            }}>{t('settings.llmAdd')}</Button>
          </div>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-muted">{t('settings.llmHint')}</p>

          {configs.data?.length === 0 && !showForm && (
            <div className="rounded-lg border border-dashed border-border-strong p-6 text-center">
              <p className="text-sm text-muted">{t('settings.llmNoConfigs')}</p>
              <Button size="sm" className="mt-3" onClick={() => setShowForm(true)}>{t('settings.llmAdd')}</Button>
            </div>
          )}

          {configs.data?.map((cfg) => (
            <div key={cfg.id} className="mb-3 rounded-lg border border-border p-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium text-text">{cfg.name}</span>
                  <span className="ml-2 rounded bg-surface-2 px-2 py-0.5 font-mono text-xs text-muted">{cfg.provider_type}</span>
                  {cfg.is_active && <span className="ml-2 rounded bg-success-bg px-2 py-0.5 text-xs text-success">active</span>}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => test.mutate(cfg.id)}
                    disabled={test.isPending}
                  >
                    {test.isPending && test.variables === cfg.id
                      ? t('settings.llmTesting')
                      : t('settings.llmTest')}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => del.mutate(cfg.id)} disabled={del.isPending}>
                    {t('common.delete')}
                  </Button>
                </div>
              </div>
              <p className="mt-1 text-xs text-muted">Model: {cfg.model} · URL: {cfg.base_url} · Key: {cfg.api_key_masked}</p>
              {test.variables === cfg.id && test.data && (
                <ConnectionResult result={test.data} />
              )}
              {test.variables === cfg.id && test.error instanceof ApiError && (
                <p className="mt-2 rounded bg-danger-bg px-3 py-2 text-xs text-danger">
                  {test.error.message}
                </p>
              )}
            </div>
          ))}

          {showForm && (
            <form className="mt-4 space-y-3 rounded-lg border border-border-strong bg-surface-2 p-4" onSubmit={(e) => {
              e.preventDefault();
              save.mutate(form, { onSuccess: () => setShowForm(false) });
            }}>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>{t('settings.llmName')}</Label><Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
                <div><Label>{t('settings.llmProviderType')}</Label>
                  <select className="h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-text" value={form.provider_type} onChange={e => setForm({...form, provider_type: e.target.value})}>
                    <option value="openai_compatible">OpenAI Compatible</option>
                    <option value="anthropic">Anthropic</option>
                  </select>
                </div>
                <div><Label>{t('settings.llmBaseUrl')}</Label><Input placeholder="https://api.openai.com/v1" value={form.base_url} onChange={e => setForm({...form, base_url: e.target.value})} /></div>
                <div><Label>{t('settings.llmModel')}</Label><Input placeholder="gpt-4o" value={form.model} onChange={e => setForm({...form, model: e.target.value})} /></div>
              </div>
              <div><Label>{t('settings.llmApiKey')}</Label><Input type="password" placeholder="sk-..." value={form.api_key} onChange={e => setForm({...form, api_key: e.target.value})} /><p className="mt-1 text-xs text-faint">{t('settings.llmApiKeyHint')}</p></div>
              <div><Label>{t('settings.llmDesc')}</Label><Input value={form.description} onChange={e => setForm({...form, description: e.target.value})} /></div>
              {save.error instanceof ApiError && <p className="text-sm text-danger">{save.error.message}</p>}
              <div className="flex gap-2 pt-2">
                <Button type="submit" size="sm" disabled={save.isPending}>{save.isPending ? '…' : t('common.save')}</Button>
                <Button type="button" size="sm" variant="secondary" onClick={() => setShowForm(false)}>{t('common.cancel')}</Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ConnectionResult({ result }: { result: LLMConnectionTest }) {
  return (
    <div
      className={cn(
        'mt-3 rounded-md border px-3 py-2 text-xs',
        result.ok
          ? 'border-success/30 bg-success-bg text-success'
          : 'border-danger/30 bg-danger-bg text-danger',
      )}
    >
      <div className="font-medium">
        {result.ok ? '✓' : '✕'} {result.message} · {result.latency_ms} ms
      </div>
      {result.sample && (
        <div className="mt-1 break-words font-mono text-[11px] opacity-80">
          {result.sample}
        </div>
      )}
    </div>
  );
}
