'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

import { listCatalog, type SkillCatalogItem } from '@/lib/api/skills';
import { ApiError } from '@/lib/api/client';
import { useI18n } from '@/lib/i18n';
import { Skeleton } from '@/components/ui/skeleton';

import { SkillCard } from './SkillCard';
import { SkillDetailPanel } from './SkillDetailPanel';
import { WhatIsSkill } from './WhatIsSkill';

export function SkillsMarketplace({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery<SkillCatalogItem[], ApiError>({
    queryKey: ['skills-catalog', projectId], queryFn: () => listCatalog(projectId),
  });

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)]">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <header className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-neutral-900">{t('skills.title')}</h2>
          <Link href={`/projects/${projectId}/skills/builder`} className="rounded-xl bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800">{t('skills.openBuilder')}</Link>
        </header>
        <WhatIsSkill />
        {isLoading && <div className="grid gap-4 sm:grid-cols-2"><Skeleton className="h-40"/><Skeleton className="h-40"/><Skeleton className="h-40"/><Skeleton className="h-40"/></div>}
        {isError && <p className="text-sm text-red-600">{t('common.error')}</p>}
        {data && data.length === 0 && <p className="text-sm text-neutral-400">{t('common.empty')}</p>}
        {data && (
          <div className="grid gap-4 sm:grid-cols-2">
            {data.map((skill) => <SkillCard key={skill.slug} projectId={projectId} skill={skill} selected={selectedSlug === skill.slug} onSelect={setSelectedSlug} />)}
          </div>
        )}
      </div>
      {selectedSlug && (
        <aside className="w-96 shrink-0 overflow-y-auto border-l border-neutral-200 bg-white p-4">
          <SkillDetailPanel projectId={projectId} slug={selectedSlug} />
        </aside>
      )}
    </div>
  );
}
