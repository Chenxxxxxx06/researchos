'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, KeyRound, Languages, Palette, Pencil, Plus, Trash2, Wifi } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ApiError } from '@/lib/api/client';
import {
  deleteLLMConfig,
  listLLMConfigs,
  saveLLMConfig,
  testLLMConfig,
  updateLLMConfig,
  type LLMConfig,
  type LLMConfigInput,
  type LLMConnectionTest,
} from '@/lib/api/llmConfig';
import { useI18n } from '@/lib/i18n';
import { useTheme, type ThemePreference } from '@/lib/theme';
import { cn } from '@/lib/utils';
import { LanguageSwitcher } from '@/features/workspace/LanguageSwitcher';

const TILE_PREVIEW: Record<ThemePreference, { canvas: string; card: string; line: string }> = {
  light: { canvas: '#f7faf7', card: '#ffffff', line: '#bbd3c2' },
  dark: { canvas: '#0c100d', card: '#181d19', line: '#41634b' },
  system: { canvas: '#f7faf7', card: '#181d19', line: '#4b8a60' },
};

export function SettingsPanel({ projectId }: { projectId: string }) {
  const { t, locale } = useI18n();
  const zh = locale === 'zh-CN';
  const { preference, setTheme } = useTheme();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm());

  const closeForm = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm());
  };

  const configs = useQuery<LLMConfig[]>({
    queryKey: ['llm-configs', projectId],
    queryFn: () => listLLMConfigs(projectId),
  });
  const save = useMutation({
    mutationFn: (input: Parameters<typeof saveLLMConfig>[1]) => saveLLMConfig(projectId, input),
    onSuccess: () => {
      closeForm();
      void queryClient.invalidateQueries({ queryKey: ['llm-configs', projectId] });
    },
  });
  const update = useMutation({
    mutationFn: ({ id, input }: { id: string; input: LLMConfigInput }) =>
      updateLLMConfig(projectId, id, input),
    onSuccess: () => {
      closeForm();
      void queryClient.invalidateQueries({ queryKey: ['llm-configs', projectId] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteLLMConfig(projectId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['llm-configs', projectId] }),
  });
  const test = useMutation({ mutationFn: (id: string) => testLLMConfig(projectId, id) });
  const themeOptions: Array<{ value: ThemePreference; label: string }> = [
    { value: 'light', label: t('theme.light') },
    { value: 'dark', label: t('theme.dark') },
    { value: 'system', label: t('theme.system') },
  ];

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,0.8fr)_minmax(34rem,1.2fr)]">
      <div className="space-y-5">
        <SettingsSection icon={Palette} title={t('settings.appearance')} description={t('settings.appearanceHint')}>
          <div role="radiogroup" aria-label={t('settings.appearance')} className="grid grid-cols-3 gap-3">
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
        </SettingsSection>
        <SettingsSection icon={Languages} title={t('settings.language')} description={t('settings.languageHint')}>
          <LanguageSwitcher />
        </SettingsSection>
        <div className="border border-success/25 bg-success-bg/50 p-4">
          <div className="flex items-start gap-3">
            <KeyRound className="mt-0.5 h-4 w-4 text-success" />
            <div>
              <p className="text-xs font-semibold text-text">{zh ? '密钥安全' : 'Secret security'}</p>
              <p className="mt-1 text-xs leading-5 text-muted">
                {zh
                  ? 'Zotero 与模型密钥在写入数据库前加密；界面与日志只显示掩码。'
                  : 'Zotero and model keys are encrypted before persistence; the UI and logs only expose masks.'}
              </p>
            </div>
          </div>
        </div>
      </div>

      <SettingsSection
        icon={Wifi}
        title={t('settings.llmTitle')}
        description={t('settings.llmHint')}
        action={
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setEditingId(null);
              setForm(emptyForm());
              setShowForm(true);
            }}
          >
            <Plus className="mr-1 h-3.5 w-3.5" />
            {t('settings.llmAdd')}
          </Button>
        }
      >
        <div className="space-y-3">
          {configs.isLoading && <p className="text-xs text-muted">{zh ? '正在读取模型配置…' : 'Loading model configurations…'}</p>}
          {configs.data?.length === 0 && !showForm && (
            <div className="border border-dashed border-border-strong p-6 text-center text-sm text-muted">
              {t('settings.llmNoConfigs')}
            </div>
          )}
          {configs.data?.map((config) => (
            <div key={config.id} className="border border-border bg-bg/50 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-text">{config.name}</p>
                    {config.is_active && (
                      <span className="inline-flex items-center gap-1 bg-success-bg px-2 py-0.5 text-[10px] font-medium text-success">
                        <CheckCircle2 className="h-3 w-3" /> active
                      </span>
                    )}
                  </div>
                  <p className="mt-1 font-mono text-[10px] text-muted">
                    {config.provider_type} · {config.model} · {config.api_key_masked}
                  </p>
                  <p className="mt-1 break-all text-[10px] text-faint">{config.base_url}</p>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setEditingId(config.id);
                      setForm(formForConfig(config));
                      setShowForm(true);
                    }}
                  >
                    <Pencil className="mr-1 h-3.5 w-3.5" />
                    {t('settings.llmEdit')}
                  </Button>
                  <Button size="sm" variant="secondary" disabled={test.isPending} onClick={() => test.mutate(config.id)}>
                    {test.isPending && test.variables === config.id ? t('settings.llmTesting') : t('settings.llmTest')}
                  </Button>
                  <Button size="sm" variant="ghost" aria-label={t('common.delete')} disabled={remove.isPending} onClick={() => remove.mutate(config.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              {test.variables === config.id && test.data && <ConnectionResult result={test.data} />}
              {test.variables === config.id && test.error instanceof ApiError && (
                <p className="mt-3 border border-danger/20 bg-danger-bg px-3 py-2 text-xs text-danger">{test.error.message}</p>
              )}
            </div>
          ))}
          {showForm && (
            <form
              className="space-y-3 border border-border-strong bg-surface-2 p-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (editingId) update.mutate({ id: editingId, input: form });
                else save.mutate(form);
              }}
            >
              <h3 className="text-sm font-semibold text-text">
                {editingId ? t('settings.llmEditTitle') : t('settings.llmAdd')}
              </h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={t('settings.llmName')}><Input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></Field>
                <Field label={t('settings.llmProviderType')}>
                  <select className="h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-text" value={form.provider_type} onChange={(event) => setForm({ ...form, provider_type: event.target.value })}>
                    <option value="openai_compatible">OpenAI Compatible</option>
                    <option value="anthropic">Anthropic</option>
                  </select>
                </Field>
                <Field label={t('settings.llmBaseUrl')}><Input required value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} /></Field>
                <Field label={t('settings.llmModel')}><Input required value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} /></Field>
              </div>
              <Field label={t('settings.llmApiKey')}>
                <Input required={!editingId} type="password" autoComplete="off" value={form.api_key} onChange={(event) => setForm({ ...form, api_key: event.target.value })} />
                {editingId && <p className="mt-1 text-[11px] text-muted">{t('settings.llmApiKeyHint')}</p>}
              </Field>
              <Field label={t('settings.llmDesc')}><Input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></Field>
              <label className="flex items-center gap-2 text-sm text-text">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
                />
                {t('settings.llmActive')}
              </label>
              {(save.error instanceof ApiError || update.error instanceof ApiError) && (
                <p className="text-xs text-danger">
                  {(editingId ? update.error : save.error)?.message}
                </p>
              )}
              <div className="flex gap-2 pt-1">
                <Button size="sm" type="submit" disabled={save.isPending || update.isPending}>
                  {editingId ? t('settings.llmSaveChanges') : t('common.save')}
                </Button>
                <Button size="sm" type="button" variant="secondary" onClick={closeForm}>{t('common.cancel')}</Button>
              </div>
            </form>
          )}
        </div>
      </SettingsSection>
    </div>
  );
}

function emptyForm() {
  return {
    name: 'default',
    provider_type: 'openai_compatible',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o',
    api_key: '',
    description: '',
    is_active: true,
  };
}

function formForConfig(config: LLMConfig) {
  return {
    name: config.name,
    provider_type: config.provider_type,
    base_url: config.base_url,
    model: config.model,
    api_key: '',
    description: config.description ?? '',
    is_active: config.is_active,
  };
}

function SettingsSection({ icon: Icon, title, description, action, children }: { icon: typeof Palette; title: string; description: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="border border-border bg-surface p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="flex h-8 w-8 items-center justify-center bg-accent/10 text-accent"><Icon className="h-4 w-4" /></span>
          <div><h2 className="text-sm font-semibold text-text">{title}</h2><p className="mt-1 text-xs leading-5 text-muted">{description}</p></div>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><Label>{label}</Label><div className="mt-1">{children}</div></div>;
}

function AppearanceTile({ value, label, selected, onSelect }: { value: ThemePreference; label: string; selected: boolean; onSelect: () => void }) {
  const preview = TILE_PREVIEW[value];
  return (
    <button type="button" role="radio" aria-checked={selected} onClick={onSelect} className={cn('flex flex-col items-center gap-2 border p-3', selected ? 'border-accent bg-accent/5' : 'border-border hover:border-border-strong')}>
      <span className="flex h-10 w-16 items-center justify-center border" style={{ background: preview.canvas, borderColor: preview.line }}>
        <span className="flex h-6 w-10 flex-col justify-center gap-1 px-1.5" style={{ background: preview.card }}>
          <span className="h-0.5 w-full" style={{ background: preview.line }} /><span className="h-0.5 w-2/3" style={{ background: preview.line }} />
        </span>
      </span>
      <span className="text-xs font-medium text-text">{label}</span>
    </button>
  );
}

function ConnectionResult({ result }: { result: LLMConnectionTest }) {
  return <div className={cn('mt-3 border px-3 py-2 text-xs', result.ok ? 'border-success/25 bg-success-bg text-success' : 'border-danger/25 bg-danger-bg text-danger')}><span className="font-medium">{result.ok ? '✓' : '✕'} {result.message} · {result.latency_ms} ms</span>{result.sample && <p className="mt-1 break-words font-mono text-[10px] opacity-80">{result.sample}</p>}</div>;
}
