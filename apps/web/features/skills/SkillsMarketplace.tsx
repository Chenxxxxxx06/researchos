'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api/client';
import { listCatalog, type SkillCatalogItem } from '@/lib/api/skills';
import { useI18n } from '@/lib/i18n';

import { SkillCard } from './SkillCard';
import { SkillDetailPanel } from './SkillDetailPanel';
import { WhatIsSkill } from './WhatIsSkill';

export function SkillsMarketplace({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery<SkillCatalogItem[], ApiError>({
    queryKey: ['skills-catalog', projectId],
    queryFn: () => listCatalog(projectId),
  });

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-neutral-900">{t('skills.title')}</h2>
        <Link href={`/projects/${projectId}/skills/builder`}>
          <Button size="sm" variant="secondary">
            {t('skills.openBuilder')}
          </Button>
        </Link>
      </header>

      <WhatIsSkill />

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="space-y-3 lg:col-span-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {t('skills.catalog')}
          </h3>

          {isLoading && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Skeleton className="h-44 w-full" />
              <Skeleton className="h-44 w-full" />
              <Skeleton className="h-44 w-full" />
              <Skeleton className="h-44 w-full" />
            </div>
          )}

          {isError && <p className="text-sm text-red-600">{t('common.error')}</p>}

          {data && data.length === 0 && (
            <p className="text-sm text-neutral-500">{t('common.empty')}</p>
          )}

          {data && data.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2">
              {data.map((skill) => (
                <SkillCard
                  key={skill.slug}
                  projectId={projectId}
                  skill={skill}
                  selected={selectedSlug === skill.slug}
                  onSelect={setSelectedSlug}
                />
              ))}
            </div>
          )}
        </section>

        <aside className="lg:col-span-1">
          {selectedSlug ? (
            <SkillDetailPanel projectId={projectId} slug={selectedSlug} />
          ) : (
            <p className="text-sm text-neutral-400">{t('common.empty')}</p>
          )}
        </aside>
      </div>
    </div>
  );
}
