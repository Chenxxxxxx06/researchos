'use client';

import { useQuery } from '@tanstack/react-query';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api/client';
import { getSkill, type SkillDetail } from '@/lib/api/skills';
import { useI18n } from '@/lib/i18n';

function Chips({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <span className="text-sm text-neutral-400">—</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((item) => (
        <span
          key={item}
          className="rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[10px] text-neutral-600"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

export function SkillDetailPanel({
  projectId,
  slug,
}: {
  projectId: string;
  slug: string;
}) {
  const { t } = useI18n();

  const { data, isLoading, isError } = useQuery<SkillDetail, ApiError>({
    queryKey: ['skill', projectId, slug],
    queryFn: () => getSkill(projectId, slug),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{data?.name ?? slug}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && <Skeleton className="h-40 w-full" />}
        {isError && <p className="text-sm text-red-600">{t('common.error')}</p>}

        {data && (
          <>
            <p className="text-sm text-neutral-600">{data.description}</p>

            <section className="space-y-1">
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                {t('skills.modules')}
              </h4>
              <Chips items={data.modules} />
            </section>

            <section className="space-y-1">
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                {t('skills.permissions')}
              </h4>
              <Chips items={data.tool_permissions} />
            </section>

            <section className="space-y-1">
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                {t('skills.workflow')}
              </h4>
              {data.workflow.length > 0 ? (
                <ol className="list-decimal space-y-0.5 pl-5 text-sm text-neutral-600">
                  {data.workflow.map((step, index) => (
                    <li key={index}>{step}</li>
                  ))}
                </ol>
              ) : (
                <span className="text-sm text-neutral-400">—</span>
              )}
            </section>

            <section className="space-y-1">
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                {t('skills.promptTemplate')}
              </h4>
              <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-neutral-200 bg-neutral-50 p-3 font-mono text-xs text-neutral-700">
                {data.prompt_template}
              </pre>
            </section>
          </>
        )}
      </CardContent>
    </Card>
  );
}
