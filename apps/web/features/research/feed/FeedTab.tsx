'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, Rss, Settings2 } from 'lucide-react';
import { useState } from 'react';

import {
  citationKey,
  getFeed,
  importPapers,
  type FeedItem,
  type FeedResponse,
} from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';

import { SearchResultCard } from '../search/SearchResultCard';
import { FollowedCategoriesEditor } from './FollowedCategoriesEditor';

const LIMIT = 20;

function dismissKey(projectId: string): string {
  return `ros_feed_dismissed_${projectId}`;
}

function loadDismissed(projectId: string): Set<string> {
  if (typeof window === 'undefined') return new Set();
  try {
    const raw = window.localStorage.getItem(dismissKey(projectId));
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function persistDismissed(projectId: string, keys: Set<string>): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(dismissKey(projectId), JSON.stringify([...keys]));
  } catch {
    /* quota / private mode — dismissal is best-effort */
  }
}

function feedScore(item: FeedItem): number | null {
  const raw = (item.extra as { score?: unknown }).score;
  return typeof raw === 'number' ? raw : null;
}

/**
 * "Latest in my areas" feed (D4). Import reuses the reference-based import
 * (CONSOLIDATION §7 — no per-item import route); dismiss is client-side
 * (localStorage) and refresh simply refetches (no server refresh route).
 */
export function FeedTab({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const [extra, setExtra] = useState<FeedItem[]>([]);
  const [moreCursor, setMoreCursor] = useState<string | null>(null);
  const [importedKeys, setImportedKeys] = useState<Set<string>>(new Set());
  const [dismissed, setDismissed] = useState<Set<string>>(() => loadDismissed(projectId));
  const [showEditor, setShowEditor] = useState(false);

  const feed = useQuery<FeedResponse>({
    queryKey: ['feed', projectId],
    queryFn: () => getFeed(projectId, { limit: LIMIT }),
  });

  const baseItems = feed.data?.items ?? [];
  const effectiveCursor = extra.length > 0 ? moreCursor : (feed.data?.next_cursor ?? null);

  const loadMore = useMutation({
    mutationFn: () => getFeed(projectId, { cursor: effectiveCursor, limit: LIMIT }),
    onSuccess: (res) => {
      setExtra((prev) => {
        const seen = new Set([...baseItems, ...prev].map((i) => citationKey(i.source, i.external_id)));
        const merged = [...prev];
        for (const it of res.items) {
          const k = citationKey(it.source, it.external_id);
          if (!seen.has(k)) {
            seen.add(k);
            merged.push(it);
          }
        }
        return merged;
      });
      setMoreCursor(res.next_cursor);
    },
  });

  const importOne = useMutation<unknown, Error, FeedItem>({
    mutationFn: (item) =>
      importPapers(projectId, [{ source: item.source, external_id: item.external_id }]),
    onSuccess: (_res, item) => {
      setImportedKeys((prev) => new Set(prev).add(citationKey(item.source, item.external_id)));
      queryClient.invalidateQueries({ queryKey: ['papers', projectId] });
    },
  });
  const [importingKey, setImportingKey] = useState<string | null>(null);

  const refresh = () => {
    setExtra([]);
    setMoreCursor(null);
    queryClient.invalidateQueries({ queryKey: ['feed', projectId] });
  };

  const dismiss = (item: FeedItem) => {
    const k = citationKey(item.source, item.external_id);
    setDismissed((prev) => {
      const next = new Set(prev).add(k);
      persistDismissed(projectId, next);
      return next;
    });
  };

  const items = [...baseItems, ...extra].filter(
    (i) => !dismissed.has(citationKey(i.source, i.external_id)),
  );
  const hasMore = Boolean(effectiveCursor);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <h2 className="text-sm font-semibold text-text">{t('research.feed.title')}</h2>
          {items.length > 0 && (
            <span className="rounded-full bg-surface-2 px-1.5 text-[10px] font-medium text-muted">{items.length}</span>
          )}
        </div>
        <div className="flex items-center gap-0.5">
          <Button
            size="icon"
            variant="ghost"
            onClick={refresh}
            aria-label={t('research.feed.refresh')}
            loading={feed.isFetching && !feed.isLoading}
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
          <Button
            size="icon"
            variant={showEditor ? 'secondary' : 'ghost'}
            onClick={() => setShowEditor((v) => !v)}
            aria-label={t('research.feed.editCategories')}
          >
            <Settings2 className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
        </div>
      </div>

      {showEditor && (
        <div className="mb-2">
          <FollowedCategoriesEditor projectId={projectId} onSaved={refresh} />
        </div>
      )}

      <div className="-mx-1 flex-1 space-y-2 overflow-y-auto px-1">
        {feed.isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}

        {feed.isError && (
          <div className="rounded-md bg-danger-bg px-3 py-2 text-xs text-danger">
            <p>{t('research.feed.failed')}</p>
            <Button size="sm" variant="ghost" className="mt-1 h-7 text-[11px]" onClick={refresh}>
              {t('research.common.retry')}
            </Button>
          </div>
        )}

        {items.map((item) => {
          const key = citationKey(item.source, item.external_id);
          return (
            <SearchResultCard
              key={key}
              projectId={projectId}
              result={item}
              variant="feed"
              inLibrary={item.in_library || importedKeys.has(key)}
              importing={importingKey === key}
              score={feedScore(item)}
              onImport={() => {
                setImportingKey(key);
                importOne.mutate(item, { onSettled: () => setImportingKey(null) });
              }}
              onDismiss={() => dismiss(item)}
            />
          );
        })}

        {hasMore && (
          <Button
            variant="secondary"
            size="sm"
            className="w-full"
            loading={loadMore.isPending}
            onClick={() => loadMore.mutate()}
          >
            {t('research.search.loadMore')}
          </Button>
        )}

        {!feed.isLoading && !feed.isError && items.length === 0 && (
          <EmptyState
            icon={Rss}
            title={t('research.feed.emptyTitle')}
            body={t('research.feed.empty')}
            actions={
              <Button size="sm" variant="secondary" onClick={() => setShowEditor(true)}>
                {t('research.feed.editCategories')}
              </Button>
            }
            className="border-none"
          />
        )}
      </div>
    </div>
  );
}
