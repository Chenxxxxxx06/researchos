'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { allowedTools, createCustomSkill, validateSkill, type CustomSkillInput } from '@/lib/api/skills';
import { ApiError } from '@/lib/api/client';
import { useI18n } from '@/lib/i18n';

import { SkillBuilderHelp } from './SkillBuilderHelp';

const MODULES = ['research', 'ide', 'experiments', 'paper'];
const tx = 'min-h-[96px] w-full rounded-lg border border-neutral-300 bg-neutral-50 px-3 py-2 text-sm placeholder:text-neutral-400 focus:border-neutral-500 focus:outline-none resize-none';

export function SkillBuilder({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const [slug, setSlug] = useState(''); const [name, setName] = useState('');
  const [version, setVersion] = useState('1.0.0'); const [category, setCategory] = useState('general');
  const [description, setDescription] = useState(''); const [modules, setModules] = useState<string[]>([]);
  const [promptTemplate, setPromptTemplate] = useState(''); const [workflow, setWorkflow] = useState('');
  const [toolPermissions, setToolPermissions] = useState<string[]>([]);
  const [configSchema, setConfigSchema] = useState('{}');
  const [showPreview, setShowPreview] = useState(false);
  const [validation, setValidation] = useState<{ valid: boolean; errors: string[] } | null>(null);
  const [saved, setSaved] = useState(false); const [saveError, setSaveError] = useState<string | null>(null);

  const tools = useQuery<string[]>({ queryKey: ['allowed-tools', projectId], queryFn: () => allowedTools(projectId) });
  const toggle = (l: string[], v: string) => l.includes(v) ? l.filter(x => x !== v) : [...l, v];

  const buildInput = (): CustomSkillInput => {
    let cfg: Record<string, unknown> = {};
    try { const p = JSON.parse(configSchema || '{}'); if (p && typeof p === 'object' && !Array.isArray(p)) cfg = p as Record<string, unknown>; } catch { /* use {} */ }
    return { slug, name, version, description, category, modules, prompt_template: promptTemplate, workflow: workflow.split('\n').map(l => l.trim()).filter(l => l.length > 0), tool_permissions: toolPermissions, config_schema: cfg };
  };

  const validate = useMutation({ mutationFn: () => validateSkill(projectId, buildInput()), onSuccess: setValidation });
  const save = useMutation({ mutationFn: () => createCustomSkill(projectId, buildInput()), onSuccess: () => { setSaved(true); setSaveError(null); }, onError: (e) => { setSaved(false); setSaveError(e instanceof ApiError ? e.message : t('common.error')); } });

  return (
    <div className="mx-auto grid max-w-5xl gap-6 p-6 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-6">
        <h1 className="text-xl font-bold tracking-tight text-neutral-900">{t('builder.title')}</h1>
        <div className="rounded-xl border border-neutral-200 bg-white p-5 space-y-4">
          <h3 className="text-sm font-semibold text-neutral-800">{t('builder.basicInfo')}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="mb-1 block text-xs font-medium text-neutral-600">{t('builder.slug')}</label><input className="h-9 w-full rounded-lg border border-neutral-300 bg-neutral-50 px-3 text-xs" value={slug} onChange={e => setSlug(e.target.value)} /></div>
            <div><label className="mb-1 block text-xs font-medium text-neutral-600">{t('common.name')}</label><input className="h-9 w-full rounded-lg border border-neutral-300 bg-neutral-50 px-3 text-xs" value={name} onChange={e => setName(e.target.value)} /></div>
            <div><label className="mb-1 block text-xs font-medium text-neutral-600">{t('builder.version')}</label><input className="h-9 w-full rounded-lg border border-neutral-300 bg-neutral-50 px-3 text-xs" value={version} onChange={e => setVersion(e.target.value)} /></div>
            <div><label className="mb-1 block text-xs font-medium text-neutral-600">{t('builder.category')}</label><input className="h-9 w-full rounded-lg border border-neutral-300 bg-neutral-50 px-3 text-xs" value={category} onChange={e => setCategory(e.target.value)} /></div>
          </div>
          <div><label className="mb-1 block text-xs font-medium text-neutral-600">{t('common.description')}</label><textarea className={tx} value={description} onChange={e => setDescription(e.target.value)} /></div>
        </div>

        <div className="rounded-xl border border-neutral-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-neutral-800 mb-3">{t('builder.modules')}</h3>
          <div className="flex flex-wrap gap-3">{MODULES.map(m => <label key={m} className="flex items-center gap-2 text-xs text-neutral-700"><input type="checkbox" checked={modules.includes(m)} onChange={() => setModules(prev => toggle(prev, m))} />{m}</label>)}</div>
        </div>

        <div className="rounded-xl border border-neutral-200 bg-white p-5 space-y-3">
          <div><label className="mb-1 block text-xs font-medium text-neutral-600">{t('builder.promptTemplate')}</label><textarea className={tx} rows={4} value={promptTemplate} onChange={e => setPromptTemplate(e.target.value)} /></div>
          <div><label className="mb-1 block text-xs font-medium text-neutral-600">{t('builder.workflow')}</label><textarea className={tx} rows={3} value={workflow} onChange={e => setWorkflow(e.target.value)} /></div>
        </div>

        <div className="rounded-xl border border-neutral-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-neutral-800 mb-3">{t('builder.toolPermissions')}</h3>
          {tools.isLoading ? <p className="text-xs text-neutral-400">{t('common.loading')}</p> : <div className="flex flex-wrap gap-3">{tools.data?.map(tool => <label key={tool} className="flex items-center gap-2 text-xs text-neutral-700"><input type="checkbox" checked={toolPermissions.includes(tool)} onChange={() => setToolPermissions(prev => toggle(prev, tool))} />{tool}</label>)}</div>}
        </div>

        <div className="rounded-xl border border-neutral-200 bg-white p-5">
          <label className="mb-1 block text-xs font-medium text-neutral-600">{t('builder.configSchema')}</label>
          <textarea className={tx} rows={2} value={configSchema} onChange={e => setConfigSchema(e.target.value)} />
        </div>

        <div className="flex flex-wrap gap-2">
          <button onClick={() => validate.mutate()} disabled={validate.isPending} className="rounded-lg border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50">{t('builder.validate')}</button>
          <button onClick={() => setShowPreview(v => !v)} className="rounded-lg border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50">{t('builder.previewManifest')}</button>
          <button onClick={() => save.mutate()} disabled={save.isPending} className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800">{t('builder.saveInstall')}</button>
        </div>

        {validation && (validation.valid ? <p className="text-sm text-emerald-600">{t('builder.valid')}</p> : <div className="text-sm text-red-600"><p>{t('builder.invalid')}</p><ul className="mt-1 list-disc pl-5">{validation.errors.map((e,i) => <li key={i}>{e}</li>)}</ul></div>)}
        {saved && <p className="text-sm text-emerald-600">{t('builder.saved')}</p>}
        {saveError && <p className="text-sm text-red-600">{saveError}</p>}
      </div>

      <div className="space-y-6">
        <SkillBuilderHelp />
        {showPreview && <div className="rounded-xl border border-neutral-200 bg-white p-4"><h3 className="mb-2 text-sm font-semibold text-neutral-800">{t('builder.previewManifest')}</h3><pre className="overflow-auto rounded bg-neutral-50 p-3 text-xs text-neutral-800">{JSON.stringify(buildInput(), null, 2)}</pre></div>}
      </div>
    </div>
  );
}
