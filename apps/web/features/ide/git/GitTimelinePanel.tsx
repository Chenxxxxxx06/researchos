'use client';

/**
 * Git timeline (D5): StatusHeader + a commit timeline where patch commits carry
 * chips back to their chat turn, a per-commit diff viewer, and inline revert.
 * Degrades to an empty state when the git backend is absent (log 404) or the
 * provider is disabled — never crashes.
 */

import { useQuery } from '@tanstack/react-query';
import { GitCommitHorizontal, History, MessageSquare } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api/client';
import {
  getGitLog,
  getGitStatus,
  shortSha,
  type GitLogResponse,
  type GitStatus,
} from '@/lib/api/git';
import { useIdeStore } from '@/lib/ide/store';
import { useI18n } from '@/lib/i18n';

import { StatusHeader } from '../GitStatusPanel';
import { CommitDiffViewer } from './CommitDiffViewer';

const PAGE = 50;

function relTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const sec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d`;
  return new Date(iso).toLocaleDateString();
}

export function GitTimelinePanel({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const selectedCommitSha = useIdeStore((s) => s.selectedCommitSha);
  const selectCommit = useIdeStore((s) => s.selectCommit);
  const revealTurn = useIdeStore((s) => s.revealTurn);
  const [limit, setLimit] = useState(PAGE);

  const status = useQuery<GitStatus, ApiError>({
    queryKey: ['git-status', projectId],
    queryFn: () => getGitStatus(projectId),
  });
  const log = useQuery<GitLogResponse, ApiError>({
    queryKey: ['git-log', projectId, limit],
    queryFn: () => getGitLog(projectId, { limit }),
  });

  const unsupported =
    (log.isError && log.error?.status === 404) || status.data?.provider === 'disabled';
  const entries = log.data?.entries ?? [];
  const hasMore = entries.length >= limit;

  return (
    <div className="flex h-full flex-col bg-bg">
      <StatusHeader projectId={projectId} />

      {selectedCommitSha ? (
        <CommitDiffViewer projectId={projectId} sha={selectedCommitSha} />
      ) : (
        <div className="flex-1 overflow-y-auto p-3">
          {log.isLoading && <Skeleton className="h-40 w-full" />}

          {log.isError && !unsupported && (
            <div className="text-sm text-danger">
              <p>{t('ide.gitFailed')}</p>
              <Button variant="outline" size="sm" className="mt-2" onClick={() => void log.refetch()}>
                {t('common.retry')}
              </Button>
            </div>
          )}

          {!log.isLoading && (unsupported || entries.length === 0) && (
            <EmptyState
              icon={History}
              title={t('ide.gitEmptyTitle')}
              body={unsupported ? t('ide.gitEmptyBody') : undefined}
            />
          )}

          {entries.length > 0 && (
            <ol className="relative ml-1 border-l border-border">
              {entries.map((entry) => (
                <li key={entry.sha} className="relative py-2 pl-5">
                  <span
                    className="absolute -left-[5px] top-3.5 h-2 w-2 rounded-full bg-border-strong"
                    aria-hidden="true"
                  />
                  <button
                    type="button"
                    onClick={() => selectCommit(entry.sha)}
                    className="block w-full text-left outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px] text-muted">{shortSha(entry.sha)}</span>
                      <span className="text-[11px] text-faint">{relTime(entry.authored_at)}</span>
                    </div>
                    <p className="truncate text-xs text-text" title={entry.summary}>
                      {entry.summary}
                    </p>
                  </button>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    {entry.patch_id && (
                      <Badge variant="info" size="sm">
                        <GitCommitHorizontal className="h-3 w-3" aria-hidden="true" />
                        {t('ide.patchChip')}
                      </Badge>
                    )}
                    {entry.agent_run_id && (
                      <button
                        type="button"
                        onClick={() => entry.agent_run_id && revealTurn(entry.agent_run_id)}
                        className="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted hover:bg-border hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
                      >
                        <MessageSquare className="h-3 w-3" aria-hidden="true" />
                        {t('ide.viewInChat')}
                      </button>
                    )}
                    {entry.reverts_sha && (
                      <Badge variant="neutral" size="sm">
                        {t('ide.revertsChip', { sha: shortSha(entry.reverts_sha) })}
                      </Badge>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}

          {hasMore && (
            <div className="mt-3 flex justify-center">
              <Button variant="outline" size="sm" onClick={() => setLimit((l) => l + PAGE)}>
                {t('ide.loadMore')}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
