'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, Library, MoreVertical, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import { deletePaper, listPapers, type Page, type Paper } from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { Dropdown, DropdownItem } from '@/components/ui/dropdown';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';

import { IngestionStatusChip } from './search/IngestionStatusChip';

const FILTER_THRESHOLD = 15;

/**
 * Library panel v1.5 (D9): in-app reading-room links, a compact ingestion dot,
 * a kebab (open original / delete-with-confirm), a client-side title filter once
 * the list grows, and a self-disabling poll while any paper is still ingesting.
 */
export function PaperLibrary({
  projectId,
  onFocusDiscover,
}: {
  projectId: string;
  onFocusDiscover?: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState('');

  const { data, isLoading, isError } = useQuery<Page<Paper>, ApiError>({
    queryKey: ['papers', projectId],
    queryFn: () => listPapers(projectId, { limit: 100 }),
    refetchInterval: (q) =>
      q.state.data?.items.some((p) => p.ingest_status === 'pending' || p.ingest_status === 'running')
        ? 4000
        : false,
  });

  const del = useMutation({
    mutationFn: (id: string) => deletePaper(projectId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['papers', projectId] }),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const filtered = filter.trim()
    ? items.filter((p) => p.title.toLowerCase().includes(filter.trim().toLowerCase()))
    : items;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-faint">{t('research.library.title')}</h3>
        {data && <span className="rounded-full bg-surface-2 px-1.5 text-[10px] font-medium text-muted">{total}</span>}
      </div>

      {isLoading && <Skeleton className="h-12 w-full" />}
      {isError && (
        <p className="text-[11px] text-danger">{t('research.library.failed')}</p>
      )}

      {!isLoading && total === 0 && (
        <EmptyState
          icon={Library}
          title={t('research.library.empty')}
          actions={
            <Button size="sm" variant="secondary" onClick={onFocusDiscover}>
              {t('research.library.emptyCta')}
            </Button>
          }
          className="border-none px-2 py-6"
        />
      )}

      {total > FILTER_THRESHOLD && (
        <Input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder={t('research.library.filter')}
          className="mb-2 h-8 text-xs"
        />
      )}

      <ul className="space-y-0.5">
        {filtered.map((paper) => (
          <li key={paper.id} className="group flex items-center gap-1.5 rounded-md px-2 py-1.5 hover:bg-surface-2">
            <IngestionStatusChip status={paper.ingest_status} variant="dot" />
            <Link
              href={`/projects/${projectId}/research/read/${paper.id}`}
              className="min-w-0 flex-1 truncate text-xs leading-snug text-text hover:underline"
              title={paper.title}
            >
              {paper.title}
            </Link>
            <Dropdown
              align="end"
              trigger={
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-6 w-6 shrink-0 opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  aria-label={paper.title}
                >
                  <MoreVertical className="h-3.5 w-3.5" aria-hidden="true" />
                </Button>
              }
            >
              <DropdownItem icon={ExternalLink} onSelect={() => window.open(paper.url, '_blank', 'noopener,noreferrer')}>
                {t('research.library.openOriginal')}
              </DropdownItem>
              <DropdownItem
                icon={Trash2}
                destructive
                onSelect={() => {
                  if (window.confirm(t('research.library.deleteConfirm'))) del.mutate(paper.id);
                }}
              >
                {t('research.library.delete')}
              </DropdownItem>
            </Dropdown>
          </li>
        ))}
      </ul>
    </div>
  );
}
