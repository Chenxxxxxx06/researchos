'use client';

import { Check, X } from 'lucide-react';
import Link from 'next/link';

import type { Paper, PaperResult } from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

import { IngestionStatusChip } from './IngestionStatusChip';
import { SourceBadge } from './SourceBadge';

function authorsLine(authors: string[]): string {
  if (authors.length === 0) return '';
  const head = authors.slice(0, 3).join(', ');
  return authors.length > 3 ? `${head} +${authors.length - 3}` : head;
}

function shortDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toISOString().slice(0, 10);
}

function ScoreBar({ score, title }: { score: number; title: string }) {
  const filled = Math.max(1, Math.min(4, Math.ceil(score * 4)));
  return (
    <Tooltip content={title}>
      <span className="inline-flex items-center gap-0.5" aria-label={title}>
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn('h-2.5 w-1.5 rounded-sm', i < filled ? 'bg-accent' : 'bg-surface-2')}
          />
        ))}
      </span>
    </Tooltip>
  );
}

export interface SearchResultCardProps {
  projectId: string;
  result: PaperResult;
  variant?: 'search' | 'feed';
  /** Full library paper when this result is in the library (enables link + chip). */
  libraryPaper?: Paper | null;
  /** Known-in-library without a resolved Paper (feed items). */
  inLibrary?: boolean;
  importing?: boolean;
  onImport: () => void;
  score?: number | null;
  onDismiss?: () => void;
}

export function SearchResultCard({
  projectId,
  result,
  variant = 'search',
  libraryPaper = null,
  inLibrary = false,
  importing = false,
  onImport,
  score = null,
  onDismiss,
}: SearchResultCardProps) {
  const { t } = useI18n();
  const date = shortDate(result.published_at);
  const isInLibrary = Boolean(libraryPaper) || inLibrary;

  return (
    <div className="rounded-lg border border-border bg-surface p-3 shadow-elev1">
      <div className="flex items-start justify-between gap-2">
        <a
          href={result.url}
          target="_blank"
          rel="noreferrer"
          className="text-xs font-semibold leading-snug text-text hover:underline"
        >
          {result.title}
        </a>
        {variant === 'feed' && score != null && (
          <ScoreBar score={score} title={t('research.feed.fitScore')} />
        )}
      </div>

      {(result.authors.length > 0 || result.venue || date) && (
        <p className="mt-1 truncate text-[11px] text-muted">
          {[authorsLine(result.authors), result.venue, date].filter(Boolean).join(' · ')}
        </p>
      )}

      {result.abstract && (
        <p className="mt-1.5 line-clamp-2 text-[11px] leading-relaxed text-muted">{result.abstract}</p>
      )}

      <div className="mt-2.5 flex items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <SourceBadge result={result} />
          {result.citation_count != null && (
            <Badge size="sm" variant="neutral">
              {t('research.search.citedBy', { n: result.citation_count })}
            </Badge>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {variant === 'feed' && onDismiss && !isInLibrary && (
            <Button size="icon" variant="ghost" onClick={onDismiss} aria-label={t('research.feed.dismiss')}>
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </Button>
          )}

          {libraryPaper ? (
            <div className="flex items-center gap-1.5">
              <IngestionStatusChip status={libraryPaper.ingest_status} />
              <Link
                href={`/projects/${projectId}/research/read/${libraryPaper.id}`}
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-success hover:bg-surface-2"
              >
                <Check className="h-3 w-3" aria-hidden="true" />
                {t('research.search.inLibrary')}
              </Link>
            </div>
          ) : inLibrary ? (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-success">
              <Check className="h-3 w-3" aria-hidden="true" />
              {t('research.search.inLibrary')}
            </span>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              className="h-7 text-[11px]"
              loading={importing}
              onClick={onImport}
            >
              {importing ? t('research.search.importing') : t('research.search.import')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
