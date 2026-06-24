'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  deleteLLMConfig,
  listLLMConfigs,
  saveLLMConfig,
  type LLMConfig,
} from '@/lib/api/llmConfig';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LanguageSwitcher } from '@/features/workspace/LanguageSwitcher';
import { ApiError } from '@/lib/api/client';
import { useParams } from 'next/navigation';

export default function SettingsPage() {
  const { t } = useI18n();
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

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: 'default',
    provider_type: 'openai_compatible',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o',
    api_key: '',
    description: '',
  });

  return (
    <div className="max-w-3xl space-y-8">
      <h1 className="text-xl font-bold tracking-tight text-neutral-900">{t('settings.title')}</h1>

      {/* Language */}
      <Card>
        <CardHeader><CardTitle>{t('settings.language')}</CardTitle></CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-neutral-500">{t('settings.languageHint')}</p>
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
          <p className="mb-4 text-sm text-neutral-500">{t('settings.llmHint')}</p>

          {configs.data?.length === 0 && !showForm && (
            <div className="rounded-lg border border-dashed border-neutral-300 p-6 text-center">
              <p className="text-sm text-neutral-500">{t('settings.llmNoConfigs')}</p>
              <Button size="sm" className="mt-3" onClick={() => setShowForm(true)}>{t('settings.llmAdd')}</Button>
            </div>
          )}

          {configs.data?.map((cfg) => (
            <div key={cfg.id} className="mb-3 rounded-lg border border-neutral-200 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium text-neutral-900">{cfg.name}</span>
                  <span className="ml-2 rounded bg-neutral-100 px-2 py-0.5 font-mono text-xs text-neutral-600">{cfg.provider_type}</span>
                  {cfg.is_active && <span className="ml-2 rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">active</span>}
                </div>
                <Button size="sm" variant="ghost" onClick={() => del.mutate(cfg.id)} disabled={del.isPending}>
                  {t('common.delete')}
                </Button>
              </div>
              <p className="mt-1 text-xs text-neutral-500">Model: {cfg.model} · URL: {cfg.base_url} · Key: {cfg.api_key_masked}</p>
            </div>
          ))}

          {showForm && (
            <form className="mt-4 rounded-lg border border-neutral-300 bg-neutral-50 p-4 space-y-3" onSubmit={(e) => {
              e.preventDefault();
              save.mutate(form, { onSuccess: () => setShowForm(false) });
            }}>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>{t('settings.llmName')}</Label><Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
                <div><Label>{t('settings.llmProviderType')}</Label>
                  <select className="h-10 w-full rounded-md border border-neutral-300 bg-white px-3 text-sm" value={form.provider_type} onChange={e => setForm({...form, provider_type: e.target.value})}>
                    <option value="openai_compatible">OpenAI Compatible</option>
                    <option value="anthropic">Anthropic</option>
                  </select>
                </div>
                <div><Label>{t('settings.llmBaseUrl')}</Label><Input placeholder="https://api.openai.com/v1" value={form.base_url} onChange={e => setForm({...form, base_url: e.target.value})} /></div>
                <div><Label>{t('settings.llmModel')}</Label><Input placeholder="gpt-4o" value={form.model} onChange={e => setForm({...form, model: e.target.value})} /></div>
              </div>
              <div><Label>{t('settings.llmApiKey')}</Label><Input type="password" placeholder="sk-..." value={form.api_key} onChange={e => setForm({...form, api_key: e.target.value})} /><p className="mt-1 text-xs text-neutral-400">{t('settings.llmApiKeyHint')}</p></div>
              <div><Label>{t('settings.llmDesc')}</Label><Input value={form.description} onChange={e => setForm({...form, description: e.target.value})} /></div>
              {save.error instanceof ApiError && <p className="text-sm text-red-600">{save.error.message}</p>}
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
