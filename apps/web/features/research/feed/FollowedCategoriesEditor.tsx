'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { getFeedCategories, putFeedCategories, type FeedCategories } from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

import { CategoryPicker } from '../search/CategoryPicker';

/**
 * Fetch/save the followed-category list around the shared `CategoryPicker`
 * (D4.3). `derived: true` means the server inferred categories from the library
 * (no explicit follow yet) — surfaced as a hint.
 */
export function FollowedCategoriesEditor({
  projectId,
  onSaved,
}: {
  projectId: string;
  onSaved?: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);

  const settings = useQuery<FeedCategories>({
    queryKey: ['feed-categories', projectId],
    queryFn: () => getFeedCategories(projectId),
  });

  useEffect(() => {
    if (settings.data && !dirty) setSelected(settings.data.categories);
  }, [settings.data, dirty]);

  const save = useMutation({
    mutationFn: () => putFeedCategories(projectId, selected),
    onSuccess: (data) => {
      queryClient.setQueryData(['feed-categories', projectId], data);
      queryClient.invalidateQueries({ queryKey: ['feed', projectId] });
      setDirty(false);
      onSaved?.();
    },
  });

  if (settings.isLoading) return <Skeleton className="h-24 w-full" />;

  return (
    <div className="space-y-2 rounded-md border border-border bg-surface p-2.5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-text">{t('research.feed.editCategories')}</p>
        {settings.data?.derived && <span className="text-[10px] text-faint">{t('research.feed.derived')}</span>}
      </div>

      <p className="text-[11px] text-muted">{t('research.feed.categoriesHint')}</p>

      <CategoryPicker
        selected={selected}
        onChange={(next) => {
          setSelected(next);
          setDirty(true);
        }}
      />

      <div className="flex items-center gap-1.5">
        <Button size="sm" className="h-7 text-[11px]" loading={save.isPending} disabled={!dirty} onClick={() => save.mutate()}>
          {t('common.save')}
        </Button>
        {dirty && (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-[11px]"
            onClick={() => {
              setSelected(settings.data?.categories ?? []);
              setDirty(false);
            }}
          >
            {t('common.cancel')}
          </Button>
        )}
      </div>
    </div>
  );
}
