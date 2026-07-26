'use client';

/**
 * Workspace grep panel (D7). Debounced (350ms, min 2 chars) → `grepWorkspace`.
 * Results grouped by file; a row opens the file at its line. A 404 reports up so
 * IdeWorkspace hides the Search tab entirely.
 */

import { useQuery } from '@tanstack/react-query';
import { Search as SearchIcon } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api/client';
import { grepWorkspace, type GrepMatch, type GrepResponse } from '@/lib/api/workspace';
import { useIdeStore } from '@/lib/ide/store';
import { useI18n } from '@/lib/i18n';

const LIMIT = 100;

export function SearchPanel({
  projectId,
  onUnsupported,
}: {
  projectId: string;
  onUnsupported?: () => void;
}) {
  const { t } = useI18n();
  const openFileAtLine = useIdeStore((s) => s.openFileAtLine);
  const [raw, setRaw] = useState('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    const id = setTimeout(() => setQuery(raw.trim()), 350);
    return () => clearTimeout(id);
  }, [raw]);

  const enabled = query.length >= 2;
  const search = useQuery<GrepResponse, ApiError>({
    queryKey: ['workspace-grep', projectId, query],
    queryFn: () => grepWorkspace(projectId, { query, limit: LIMIT }),
    enabled,
    retry: (_count, err) => !(err instanceof ApiError && err.status === 404),
  });

  const notFound = search.error instanceof ApiError && search.error.status === 404;
  useEffect(() => {
    if (notFound) onUnsupported?.();
  }, [notFound, onUnsupported]);

  const grouped = useMemo(() => {
    const map = new Map<string, GrepMatch[]>();
    for (const match of search.data?.matches ?? []) {
      const list = map.get(match.path) ?? [];
      list.push(match);
      map.set(match.path, list);
    }
    return [...map.entries()];
  }, [search.data]);

  return (
    <div className="flex h-full flex-col">
      <div className="p-2">
        <div className="relative">
          <SearchIcon
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint"
            aria-hidden="true"
          />
          <Input
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            placeholder={t('ide.searchPlaceholder')}
            aria-label={t('ide.search')}
            className="h-9 pl-8 text-sm"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {!enabled && <p className="px-1 py-2 text-xs text-muted">{t('ide.searchHint')}</p>}

        {enabled && search.isLoading && <Skeleton className="mx-1 h-24" />}

        {enabled && notFound && (
          <p className="px-1 py-2 text-xs text-muted">{t('ide.searchUnavailable')}</p>
        )}

        {enabled && search.isError && !notFound && (
          <p className="px-1 py-2 text-xs text-danger">{t('ide.searchFailed')}</p>
        )}

        {enabled && search.data && search.data.matches.length === 0 && (
          <EmptyState className="mt-4 border-none" title={t('ide.searchNoMatches')} />
        )}

        {grouped.map(([path, matches]) => (
          <div key={path} className="mt-2 first:mt-1">
            <p className="truncate px-1 font-mono text-[11px] font-medium text-muted" title={path}>
              {path}
            </p>
            <ul>
              {matches.map((m, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => openFileAtLine(m.path, m.line)}
                    className="flex w-full items-baseline gap-2 rounded px-1 py-0.5 text-left hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
                  >
                    <span className="w-8 shrink-0 text-right font-mono text-[10px] text-faint tabular-nums">
                      {m.line}
                    </span>
                    <span className="truncate font-mono text-xs text-text">{m.preview}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}

        {search.data?.truncated && (
          <p className="mt-2 px-1 text-[11px] text-muted">{t('ide.searchTruncated', { limit: LIMIT })}</p>
        )}
      </div>
    </div>
  );
}
