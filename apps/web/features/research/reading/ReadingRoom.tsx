'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ExternalLink, FileText, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { ApiError } from '@/lib/api/client';
import {
  citationKey,
  getPaper,
  getPaperSections,
  reingestPaper,
  type Paper,
  type PaperSection,
  type SectionsResponse,
} from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';

import { useChatSeedStore } from '../chatSeed';
import { IngestionStatusChip } from '../search/IngestionStatusChip';
import { SectionCard } from './SectionCard';
import { SectionOutline } from './SectionOutline';

function authorsLine(authors: string[]): string {
  if (authors.length === 0) return '';
  const head = authors.slice(0, 6).join(', ');
  return authors.length > 6 ? `${head} +${authors.length - 6}` : head;
}

function shortDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toISOString().slice(0, 10);
}

/**
 * In-app paper detail with sectioned full text (D5). Consumes the real sections
 * vocabulary (`pending|running|succeeded|abstract_only|failed`), converges via a
 * 4s poll while ingesting, and hands "Explain this / Explain paper" off to the
 * research chat by setting the chat seed and navigating back to `/research`.
 */
export function ReadingRoom({ projectId, paperId }: { projectId: string; paperId: string }) {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const setSeed = useChatSeedStore((s) => s.setSeed);

  const paper = useQuery<Paper, ApiError>({
    queryKey: ['paper', projectId, paperId],
    queryFn: () => getPaper(projectId, paperId),
    retry: false,
  });

  const sections = useQuery<SectionsResponse, ApiError>({
    queryKey: ['paper-sections', projectId, paperId],
    queryFn: () => getPaperSections(projectId, paperId),
    retry: false,
    refetchInterval: (q) => {
      const s = q.state.data?.ingest_status;
      return s === 'pending' || s === 'running' ? 4000 : false;
    },
  });

  const retry = useMutation({
    mutationFn: () => reingestPaper(projectId, paperId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper-sections', projectId, paperId] });
      queryClient.invalidateQueries({ queryKey: ['paper', projectId, paperId] });
    },
  });

  const backHref = `/projects/${projectId}/research`;

  if (paper.isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 p-6">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (paper.isError || !paper.data) {
    const notFound = paper.error?.status === 404;
    return (
      <div className="mx-auto max-w-4xl p-6">
        <Link href={backHref} className="mb-4 inline-flex items-center gap-1 text-xs text-muted hover:text-text">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          {t('research.reading.back')}
        </Link>
        <EmptyState
          title={notFound ? t('research.reading.notFound') : t('research.reading.failed')}
          actions={
            !notFound && (
              <Button size="sm" variant="secondary" onClick={() => paper.refetch()}>
                {t('research.common.retry')}
              </Button>
            )
          }
        />
      </div>
    );
  }

  const p = paper.data;
  const status = sections.data?.ingest_status ?? p.ingest_status;
  const key = citationKey(p.source, p.external_id);
  const date = shortDate(p.published_at);

  const explainPaper = () => {
    setSeed({ kind: 'paper', paperId: p.id, paperTitle: p.title, citationKey: key });
    router.push(backHref);
  };
  const explainSection = (section: PaperSection) => {
    setSeed({
      kind: 'section',
      paperId: p.id,
      paperTitle: p.title,
      citationKey: key,
      sectionSeq: section.seq,
      sectionHeading: section.heading,
    });
    router.push(backHref);
  };

  // Abstract-only papers still get a single readable/explainable section.
  const abstractSection: PaperSection = {
    seq: 0,
    level: 1,
    kind: 'abstract',
    heading: t('research.reading.abstract'),
    body: p.abstract ?? '',
    char_count: (p.abstract ?? '').length,
  };
  const stream: PaperSection[] =
    status === 'abstract_only' ? [abstractSection] : (sections.data?.sections ?? []);

  return (
    <div className="mx-auto max-w-5xl p-6">
      {/* Header */}
      <header className="mb-6 border-b border-border pb-4">
        <Link href={backHref} className="mb-3 inline-flex items-center gap-1 text-xs text-muted hover:text-text">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          {t('research.reading.back')}
        </Link>
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-xl font-semibold leading-tight text-text">{p.title}</h1>
          <Button size="sm" variant="secondary" className="shrink-0" onClick={explainPaper}>
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            {t('research.reading.explainPaper')}
          </Button>
        </div>
        {(p.authors_json.length > 0 || p.venue || date) && (
          <p className="mt-1.5 text-sm text-muted">
            {[authorsLine(p.authors_json), p.venue, date].filter(Boolean).join(' · ')}
          </p>
        )}
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <IngestionStatusChip status={status} />
          {p.url && (
            <a
              href={p.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted hover:text-text"
            >
              {p.source === 'arxiv' ? 'arXiv' : p.source} <ExternalLink className="h-3 w-3" aria-hidden="true" />
            </a>
          )}
          {p.pdf_url && (
            <a
              href={p.pdf_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted hover:text-text"
            >
              <FileText className="h-3 w-3" aria-hidden="true" /> {t('research.reading.pdf')}
            </a>
          )}
        </div>
      </header>

      {/* Body */}
      {status === 'failed' ? (
        <div className="rounded-lg bg-danger-bg px-4 py-3 text-sm text-danger">
          <p>{sections.data?.ingest_error || t('research.reading.failedNote')}</p>
          <Button size="sm" variant="secondary" className="mt-2" loading={retry.isPending} onClick={() => retry.mutate()}>
            {t('research.ingest.retry')}
          </Button>
        </div>
      ) : status === 'pending' || status === 'running' ? (
        <div className="space-y-4">
          <p className="rounded-md bg-warn-bg px-3 py-2 text-xs text-warn">{t('research.reading.pendingBody')}</p>
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-6 w-1/4" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : stream.length === 0 ? (
        <EmptyState title={t('research.reading.noSections')} className="border-none" />
      ) : (
        <div className="flex gap-6">
          <SectionOutline sections={stream} />
          <div className="min-w-0 flex-1 space-y-5">
            {status === 'abstract_only' && (
              <p className="rounded-md bg-surface-2 px-3 py-2 text-xs text-muted">
                {t('research.reading.abstractOnlyNote')}
              </p>
            )}
            {stream.map((s) => (
              <SectionCard key={s.seq} section={s} onExplain={() => explainSection(s)} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
