'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Search, X } from 'lucide-react';
import { useMemo, useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  citationKey,
  importPapers,
  listPapers,
  searchPapers,
  type Page,
  type Paper,
  type PaperResult,
} from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';

import { providerLabel } from './SourceBadge';
import { SearchResultCard } from './SearchResultCard';
import {
  EMPTY_FILTERS,
  hasAnyFilter,
  QueryBuilder,
  toApiFilters,
  type SearchFormFilters,
} from './QueryBuilder';

const LIMIT = 20;

/**
 * Fielded federated-search console (D2). Owns the query, filters, accumulated
 * result pages, dedup guard, provider-error notice and load-more pagination.
 * `has_more` / `provider_errors` / `in_library` are derived client-side from the
 * `{results, provider_status}` response and the shared library cache
 * (CONSOLIDATION §7).
 */
export function SearchPanel({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<SearchFormFilters>(EMPTY_FILTERS);
  const [results, setResults] = useState<PaperResult[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [providerErrors, setProviderErrors] = useState<string[]>([]);
  const [dismissedErrors, setDismissedErrors] = useState(false);
  const [importingKey, setImportingKey] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const library = useQuery<Page<Paper>>({
    queryKey: ['papers', projectId],
    queryFn: () => listPapers(projectId, { limit: 100 }),
  });
  const libMap = useMemo(() => {
    const m = new Map<string, Paper>();
    for (const p of library.data?.items ?? []) m.set(citationKey(p.source, p.external_id), p);
    return m;
  }, [library.data]);

  const search = useMutation<
    Awaited<ReturnType<typeof searchPapers>>,
    ApiError,
    { offset: number }
  >({
    mutationFn: (vars) =>
      searchPapers(projectId, {
        query: query.trim(),
        limit: LIMIT,
        filters: { ...toApiFilters(filters), offset: vars.offset },
      }),
    onSuccess: (res, vars) => {
      const errs = Object.entries(res.provider_status)
        .filter(([, v]) => v !== 'ok')
        .map(([k]) => k);
      setProviderErrors(errs);
      setDismissedErrors(false);
      setHasMore(res.results.length >= LIMIT);
      setResults((prev) => {
        const base = vars.offset === 0 ? [] : prev;
        const seen = new Set(base.map((r) => citationKey(r.source, r.external_id)));
        const merged = [...base];
        for (const r of res.results) {
          const k = citationKey(r.source, r.external_id);
          if (!seen.has(k)) {
            seen.add(k);
            merged.push(r);
          }
        }
        return merged;
      });
      setOffset(vars.offset);
      setSubmitted(true);
    },
  });

  const importOne = useMutation<unknown, ApiError, PaperResult>({
    mutationFn: (r) => importPapers(projectId, [{ source: r.source, external_id: r.external_id }]),
    onMutate: (r) => setImportingKey(citationKey(r.source, r.external_id)),
    onSettled: () => setImportingKey(null),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['papers', projectId] }),
  });

  const canSubmit = query.trim().length > 0 || hasAnyFilter(filters);
  const submit = () => {
    if (!canSubmit || search.isPending) return;
    setOffset(0);
    search.mutate({ offset: 0 });
  };

  const rateLimited = search.error?.status === 429;

  return (
    <div className="flex h-full flex-col">
      <h2 className="mb-2 text-sm font-semibold text-text">{t('research.search.title')}</h2>

      <form
        className="mb-2 flex gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('research.search.placeholder')}
          className="h-9 text-xs"
          aria-label={t('research.search.search')}
        />
        <Button size="sm" type="submit" className="h-9 shrink-0" disabled={!canSubmit} loading={search.isPending}>
          <Search className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      </form>

      <div className="mb-2">
        <QueryBuilder filters={filters} onChange={setFilters} />
      </div>

      {providerErrors.length > 0 && !dismissedErrors && (
        <div className="mb-2 flex items-start justify-between gap-2 rounded-md bg-warn-bg px-2.5 py-1.5 text-[11px] text-warn">
          <span>
            {t('research.search.providerError', {
              source: providerErrors.map(providerLabel).join(', '),
            })}
          </span>
          <button type="button" onClick={() => setDismissedErrors(true)} aria-label={t('research.feed.dismiss')}>
            <X className="h-3 w-3 shrink-0" aria-hidden="true" />
          </button>
        </div>
      )}

      <div className="-mx-1 flex-1 space-y-2 overflow-y-auto px-1">
        {search.isPending && offset === 0 && (
          <div className="space-y-2">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}

        {search.isError && (
          <div className="rounded-md bg-danger-bg px-3 py-2 text-xs text-danger">
            <p>{rateLimited ? t('research.search.rateLimited') : t('research.search.failed')}</p>
            <Button size="sm" variant="ghost" className="mt-1 h-7 text-[11px]" onClick={submit}>
              {t('research.common.retry')}
            </Button>
          </div>
        )}

        {results.map((r) => {
          const key = citationKey(r.source, r.external_id);
          return (
            <SearchResultCard
              key={key}
              projectId={projectId}
              result={r}
              libraryPaper={libMap.get(key) ?? null}
              importing={importingKey === key}
              onImport={() => importOne.mutate(r)}
            />
          );
        })}

        {hasMore && !search.isPending && (
          <Button
            variant="secondary"
            size="sm"
            className="w-full"
            onClick={() => search.mutate({ offset: offset + LIMIT })}
          >
            {t('research.search.loadMore')}
          </Button>
        )}
        {search.isPending && offset > 0 && <Skeleton className="h-24 w-full" />}

        {submitted && !search.isPending && !search.isError && results.length === 0 && (
          <p className="py-6 text-center text-xs text-muted">{t('research.search.noResults')}</p>
        )}

        {!submitted && !search.isPending && (
          <EmptyState
            icon={Search}
            title={t('research.search.emptyTitle')}
            body={t('research.search.emptyBody')}
            className="border-none"
          />
        )}
      </div>
    </div>
  );
}
