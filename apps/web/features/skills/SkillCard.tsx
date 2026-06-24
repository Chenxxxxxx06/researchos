'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ApiError } from '@/lib/api/client';
import { installSkill, toggleSkill, type SkillCatalogItem } from '@/lib/api/skills';
import { useI18n } from '@/lib/i18n';

export function SkillCard({
  projectId,
  skill,
  selected,
  onSelect,
}: {
  projectId: string;
  skill: SkillCatalogItem;
  selected: boolean;
  onSelect: (slug: string) => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['skills-catalog', projectId] });
    queryClient.invalidateQueries({ queryKey: ['skill', projectId, skill.slug] });
  };

  const install = useMutation<void, ApiError>({
    mutationFn: () => installSkill(projectId, skill.slug),
    onSuccess: invalidate,
  });

  const toggle = useMutation<void, ApiError>({
    mutationFn: () => toggleSkill(projectId, skill.slug, !skill.enabled),
    onSuccess: invalidate,
  });

  return (
    <Card className={selected ? 'ring-2 ring-neutral-400' : undefined}>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <button
            type="button"
            onClick={() => onSelect(skill.slug)}
            className="text-left text-sm font-semibold text-neutral-900 hover:underline"
          >
            {skill.name}
          </button>
          <span className="shrink-0 rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-neutral-600">
            {skill.visibility === 'first_party'
              ? t('skills.firstParty')
              : t('skills.custom')}
          </span>
        </div>

        <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-400">
          {skill.category}
        </p>

        <p className="line-clamp-2 text-sm text-neutral-600">{skill.description}</p>

        {skill.modules.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {skill.modules.map((module) => (
              <span
                key={module}
                className="rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[10px] text-neutral-600"
              >
                {module}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between gap-2 pt-1">
          {skill.installed ? (
            <>
              <span className="text-xs text-neutral-500">
                {skill.enabled ? t('skills.enabled') : t('skills.disabled')}
              </span>
              <Button
                size="sm"
                variant={skill.enabled ? 'secondary' : 'primary'}
                onClick={() => toggle.mutate()}
                disabled={toggle.isPending}
              >
                {skill.enabled ? t('skills.disable') : t('skills.enable')}
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              onClick={() => install.mutate()}
              disabled={install.isPending}
            >
              {t('skills.install')}
            </Button>
          )}
        </div>

        {(install.isError || toggle.isError) && (
          <p className="text-xs text-red-600">{t('common.error')}</p>
        )}
      </CardContent>
    </Card>
  );
}
