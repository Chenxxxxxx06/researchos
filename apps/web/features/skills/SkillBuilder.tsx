'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ApiError } from '@/lib/api/client';
import {
  allowedTools,
  createCustomSkill,
  validateSkill,
  type CustomSkillInput,
} from '@/lib/api/skills';
import { useI18n } from '@/lib/i18n';

import { SkillBuilderHelp } from './SkillBuilderHelp';

const MODULE_OPTIONS = ['research', 'ide', 'experiments', 'paper'];

const textareaClass =
  'min-h-[96px] w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm ' +
  'placeholder:text-neutral-400 focus-visible:outline-none focus-visible:ring-2 ' +
  'focus-visible:ring-neutral-400 disabled:opacity-50';

export function SkillBuilder({ projectId }: { projectId: string }) {
  const { t } = useI18n();

  const [slug, setSlug] = useState('');
  const [name, setName] = useState('');
  const [version, setVersion] = useState('1.0.0');
  const [category, setCategory] = useState('general');
  const [description, setDescription] = useState('');
  const [modules, setModules] = useState<string[]>([]);
  const [promptTemplate, setPromptTemplate] = useState('');
  const [workflow, setWorkflow] = useState('');
  const [toolPermissions, setToolPermissions] = useState<string[]>([]);
  const [configSchema, setConfigSchema] = useState('{}');

  const [configError, setConfigError] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [validation, setValidation] = useState<{ valid: boolean; errors: string[] } | null>(null);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const tools = useQuery<string[]>({
    queryKey: ['allowed-tools', projectId],
    queryFn: () => allowedTools(projectId),
  });

  const toggle = (list: string[], value: string): string[] =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  const parseConfig = (): { value: Record<string, unknown>; ok: boolean } => {
    try {
      const candidate = JSON.parse(configSchema || '{}');
      if (candidate && typeof candidate === 'object' && !Array.isArray(candidate)) {
        return { value: candidate as Record<string, unknown>, ok: true };
      }
      return { value: {}, ok: false };
    } catch {
      return { value: {}, ok: false };
    }
  };

  const buildInput = (): CustomSkillInput => {
    const config = parseConfig();

    return {
      slug,
      name,
      version,
      description,
      category,
      modules,
      prompt_template: promptTemplate,
      workflow: workflow
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line.length > 0),
      tool_permissions: toolPermissions,
      config_schema: config.value,
    };
  };

  const validate = useMutation({
    mutationFn: () => {
      setConfigError(parseConfig().ok ? null : t('common.error'));
      return validateSkill(projectId, buildInput());
    },
    onSuccess: (result) => setValidation(result),
  });

  const save = useMutation({
    mutationFn: () => {
      setConfigError(parseConfig().ok ? null : t('common.error'));
      return createCustomSkill(projectId, buildInput());
    },
    onSuccess: () => {
      setSaved(true);
      setSaveError(null);
    },
    onError: (err) => {
      setSaved(false);
      setSaveError(err instanceof ApiError ? err.message : t('common.error'));
    },
  });

  return (
    <div className="mx-auto grid max-w-5xl gap-6 p-6 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-6">
        <h1 className="text-lg font-semibold text-neutral-900">{t('builder.title')}</h1>

        <Card>
          <CardHeader>
            <CardTitle>{t('builder.basicInfo')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="slug">{t('builder.slug')}</Label>
              <Input id="slug" value={slug} onChange={(e) => setSlug(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="name">{t('common.name')}</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="version">{t('builder.version')}</Label>
                <Input
                  id="version"
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="category">{t('builder.category')}</Label>
                <Input
                  id="category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="description">{t('common.name')}</Label>
              <textarea
                id="description"
                className={textareaClass}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('builder.modules')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {MODULE_OPTIONS.map((mod) => (
                <label key={mod} className="flex items-center gap-2 text-sm text-neutral-700">
                  <input
                    type="checkbox"
                    checked={modules.includes(mod)}
                    onChange={() => setModules((prev) => toggle(prev, mod))}
                  />
                  {mod}
                </label>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('builder.promptTemplate')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="prompt-template">{t('builder.promptTemplate')}</Label>
              <textarea
                id="prompt-template"
                className={textareaClass}
                value={promptTemplate}
                onChange={(e) => setPromptTemplate(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="workflow">{t('builder.workflow')}</Label>
              <textarea
                id="workflow"
                className={textareaClass}
                value={workflow}
                onChange={(e) => setWorkflow(e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('builder.toolPermissions')}</CardTitle>
          </CardHeader>
          <CardContent>
            {tools.isLoading ? (
              <p className="text-sm text-neutral-500">{t('common.loading')}</p>
            ) : (
              <div className="flex flex-wrap gap-3">
                {tools.data?.map((tool) => (
                  <label
                    key={tool}
                    className="flex items-center gap-2 text-sm text-neutral-700"
                  >
                    <input
                      type="checkbox"
                      checked={toolPermissions.includes(tool)}
                      onChange={() => setToolPermissions((prev) => toggle(prev, tool))}
                    />
                    {tool}
                  </label>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('builder.configSchema')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Label htmlFor="config-schema">{t('builder.configSchema')}</Label>
            <textarea
              id="config-schema"
              className={textareaClass}
              value={configSchema}
              onChange={(e) => setConfigSchema(e.target.value)}
            />
            {configError && <p className="mt-2 text-sm text-red-600">{configError}</p>}
          </CardContent>
        </Card>

        <div className="flex flex-wrap gap-3">
          <Button
            variant="secondary"
            disabled={validate.isPending}
            onClick={() => validate.mutate()}
          >
            {t('builder.validate')}
          </Button>
          <Button variant="secondary" onClick={() => setShowPreview((v) => !v)}>
            {t('builder.previewManifest')}
          </Button>
          <Button disabled={save.isPending} onClick={() => save.mutate()}>
            {t('builder.saveInstall')}
          </Button>
        </div>

        {validation && (
          <div className="text-sm">
            {validation.valid ? (
              <p className="text-green-600">{t('builder.valid')}</p>
            ) : (
              <div className="text-red-600">
                <p>{t('builder.invalid')}</p>
                <ul className="mt-1 list-disc pl-5">
                  {validation.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {saved && <p className="text-sm text-green-600">{t('builder.saved')}</p>}
        {saveError && <p className="text-sm text-red-600">{saveError}</p>}
      </div>

      <div className="space-y-6">
        <SkillBuilderHelp />

        {showPreview && (
          <Card>
            <CardHeader>
              <CardTitle>{t('builder.previewManifest')}</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="overflow-auto rounded bg-neutral-50 p-3 text-xs text-neutral-800">
                {JSON.stringify(buildInput(), null, 2)}
              </pre>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
