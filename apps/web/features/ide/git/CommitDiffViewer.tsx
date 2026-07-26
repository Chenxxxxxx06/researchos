'use client';

/**
 * Per-commit diff (D5). Fetches `getCommitDiff(sha)` and renders each file with
 * the same FileDiffSection/HunkView renderer used for patches — the hunks are
 * computed client-side from `old_content` vs `new_content` (checkboxes off).
 */

import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api/client';
import {
  getCommitDiff,
  shortSha,
  type GitCommitDiff,
  type GitCommitDiffFile,
} from '@/lib/api/git';
import {
  diffLines,
  diffStats,
  diffTooLarge,
  groupHunks,
  type FileDiffModel,
} from '@/lib/ide/diff';
import { useIdeStore } from '@/lib/ide/store';
import { useI18n } from '@/lib/i18n';

import { FileDiffSection } from '../chat/FileDiffSection';
import { RevertRow } from './RevertRow';

function gitFileModel(file: GitCommitDiffFile): FileDiffModel {
  const base = file.old_content ?? '';
  const modified = file.new_content ?? '';
  if (file.omitted || diffTooLarge(base, modified)) {
    return { hunks: [], additions: 0, deletions: 0, source: 'whole', tooLarge: true, base, modified };
  }
  const lines = diffLines(base, modified);
  const { additions, deletions } = diffStats(lines);
  return { hunks: groupHunks(lines), additions, deletions, source: 'computed', tooLarge: false, base, modified };
}

export function CommitDiffViewer({ projectId, sha }: { projectId: string; sha: string }) {
  const { t } = useI18n();
  const openFileAtLine = useIdeStore((s) => s.openFileAtLine);
  const selectCommit = useIdeStore((s) => s.selectCommit);

  const commit = useQuery<GitCommitDiff, ApiError>({
    queryKey: ['git-commit', projectId, sha],
    queryFn: () => getCommitDiff(projectId, sha),
  });

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => selectCommit(null)}
          aria-label={t('common.cancel')}
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        </Button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-text" title={commit.data?.summary}>
            {commit.data?.summary ?? shortSha(sha)}
          </p>
          <p className="font-mono text-[11px] text-muted">{shortSha(sha)}</p>
        </div>
        <RevertRow projectId={projectId} sha={sha} />
      </div>

      <div className="flex-1 overflow-y-auto">
        {commit.isLoading && (
          <div className="p-3">
            <Skeleton className="h-24 w-full" />
          </div>
        )}
        {commit.isError && (
          <div className="p-3 text-sm text-danger">
            <p>{t('ide.commitFailed')}</p>
            <Button variant="outline" size="sm" className="mt-2" onClick={() => void commit.refetch()}>
              {t('common.retry')}
            </Button>
          </div>
        )}
        {commit.data && commit.data.files.length === 0 && (
          <p className="p-3 text-xs text-muted">{t('ide.noDiff')}</p>
        )}
        {commit.data?.files.map((file, i) => (
          <FileDiffSection
            key={file.path}
            path={file.path}
            changeType={file.change_type}
            model={gitFileModel(file)}
            defaultCollapsed={i >= 3}
            onOpenAtLine={(line) => openFileAtLine(file.path, line)}
          />
        ))}
      </div>
    </div>
  );
}
