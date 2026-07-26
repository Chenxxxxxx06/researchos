'use client';

/**
 * Inline diff card (D3.4). Renders a patch entirely from its recorded
 * `base_content` / server `hunks` / `new_content` — never the live file, so the
 * historical misleading-diff bug (gap #36) cannot recur. Per-file checkboxes
 * drive FILE-granularity partial apply (CONSOLIDATION §2); hunk-level selection
 * is display-only this session. Apply/Reject hit the existing endpoints and flip
 * the status pill in place.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, GitCommitHorizontal } from 'lucide-react';
import { useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';
import { ApiError } from '@/lib/api/client';
import { shortSha } from '@/lib/api/git';
import {
  applyPatch,
  getPatch,
  rejectPatch,
  type ApplyResult,
  type Patch,
  type PatchFile,
  type PatchStatus,
} from '@/lib/api/patches';
import { resolveFileHunks, type FileDiffModel } from '@/lib/ide/diff';
import { languageForPath } from '@/lib/ide/language';
import { ThemedMonacoDiff } from '@/lib/ide/monaco';
import { useIdeStore } from '@/lib/ide/store';
import { useI18n } from '@/lib/i18n';
import type { DictKey } from '@/lib/i18n';

import { FileDiffSection } from './FileDiffSection';

const COLLAPSE_AFTER = 3;

const STATUS_LABEL: Record<PatchStatus, DictKey> = {
  pending: 'ide.patchPending',
  applied: 'ide.patchApplied',
  rejected: 'ide.patchRejected',
  conflict: 'ide.patchConflict',
};

function statusVariant(status: PatchStatus): 'warn' | 'success' | 'neutral' | 'danger' {
  if (status === 'applied') return 'success';
  if (status === 'rejected') return 'neutral';
  if (status === 'conflict') return 'danger';
  return 'warn';
}

export function DiffCard({ projectId, patchId }: { projectId: string; patchId: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const openFileAtLine = useIdeStore((s) => s.openFileAtLine);
  const selectCommit = useIdeStore((s) => s.selectCommit);

  const patch = useQuery<Patch, ApiError>({
    queryKey: ['patch', projectId, patchId],
    queryFn: () => getPatch(projectId, patchId),
  });

  const [deselected, setDeselected] = useState<Set<string>>(new Set());
  const [partialUnsupported, setPartialUnsupported] = useState(false);
  const [fullDiffFile, setFullDiffFile] = useState<PatchFile | null>(null);

  const models = useMemo(() => {
    const map = new Map<string, FileDiffModel>();
    for (const file of patch.data?.files ?? []) map.set(file.id, resolveFileHunks(file));
    return map;
  }, [patch.data]);

  const files = patch.data?.files ?? [];
  const status = patch.data?.status;
  const selectable = status === 'pending' && !partialUnsupported && files.length > 1;
  const selectedPaths = files.filter((f) => !deselected.has(f.path)).map((f) => f.path);
  const allSelected = deselected.size === 0;

  const totals = useMemo(() => {
    let additions = 0;
    let deletions = 0;
    for (const model of models.values()) {
      additions += model.additions;
      deletions += model.deletions;
    }
    return { additions, deletions };
  }, [models]);

  const apply = useMutation({
    mutationFn: () => applyPatch(projectId, patchId, allSelected ? undefined : selectedPaths),
    onSuccess: (result: ApplyResult) => {
      queryClient.setQueryData<Patch>(['patch', projectId, patchId], (old) =>
        old
          ? {
              ...old,
              status: result.status,
              conflicts: result.conflicts,
              applied_commit_sha: result.applied_commit_sha,
            }
          : old,
      );
      void queryClient.invalidateQueries({ queryKey: ['patches', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['workspace-tree', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['file', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['git-status', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['git-log', projectId] });
      if (result.skipped_paths.length > 0) {
        toast({ title: t('ide.skippedPaths', { n: result.skipped_paths.length }) });
      }
    },
    onError: (err) => {
      // Partial apply unsupported → hide checkboxes, fall back to apply-all.
      if (err instanceof ApiError && (err.status === 422 || err.status === 400) && !allSelected) {
        setPartialUnsupported(true);
        setDeselected(new Set());
        toast({ title: t('ide.partialUnavailable'), variant: 'warning' });
        return;
      }
      toast({
        title: t('ide.patchFailed'),
        description: err instanceof Error ? err.message : undefined,
        variant: 'error',
      });
    },
  });

  const reject = useMutation({
    mutationFn: () => rejectPatch(projectId, patchId),
    onSuccess: (updated: Patch) => {
      queryClient.setQueryData(['patch', projectId, patchId], updated);
      void queryClient.invalidateQueries({ queryKey: ['patches', projectId] });
    },
    onError: (err) => {
      toast({
        title: t('ide.patchFailed'),
        description: err instanceof Error ? err.message : undefined,
        variant: 'error',
      });
    },
  });

  if (patch.isLoading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-3">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="mt-2 h-16 w-full" />
      </div>
    );
  }

  if (patch.isError || !patch.data) {
    return (
      <div className="rounded-lg border border-danger/40 bg-danger-bg p-3 text-sm text-danger">
        <p>{t('ide.patchFailed')}</p>
        <Button variant="outline" size="sm" className="mt-2" onClick={() => void patch.refetch()}>
          {t('common.retry')}
        </Button>
      </div>
    );
  }

  const data = patch.data;
  const conflicts = data.conflicts;
  const canApply = status === 'pending';
  const canReject = status === 'pending' || status === 'conflict';
  const fullDiffModel = fullDiffFile ? models.get(fullDiffFile.id) : undefined;

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-text" title={data.summary}>
          {data.summary || t('ide.proposePatch')}
        </span>
        {status && (
          <Badge variant={statusVariant(status)} size="sm" dot>
            {t(STATUS_LABEL[status])}
          </Badge>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5 text-xs text-muted">
        <span>{t(files.length === 1 ? 'ide.fileCount' : 'ide.filesCount', { n: files.length })}</span>
        <span className="font-mono">
          <span className="text-success">+{totals.additions}</span>{' '}
          <span className="text-danger">-{totals.deletions}</span>
        </span>
        {data.applied_commit_sha && (
          <button
            type="button"
            onClick={() => selectCommit(data.applied_commit_sha)}
            className="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-text hover:bg-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
            title={t('ide.viewCommit', { sha: shortSha(data.applied_commit_sha) })}
          >
            <GitCommitHorizontal className="h-3 w-3" aria-hidden="true" />
            {shortSha(data.applied_commit_sha)}
          </button>
        )}
      </div>

      {/* Files */}
      {files.length === 0 ? (
        <div className="px-3 py-3 text-xs text-muted">{t('ide.noDiff')}</div>
      ) : (
        <div>
          {files.map((file, i) => {
            const model = models.get(file.id);
            if (!model) return null;
            return (
              <FileDiffSection
                key={file.id}
                path={file.path}
                changeType={file.change_type}
                model={model}
                defaultCollapsed={i >= COLLAPSE_AFTER}
                selectable={selectable}
                selected={!deselected.has(file.path)}
                onToggleSelected={() =>
                  setDeselected((prev) => {
                    const next = new Set(prev);
                    if (next.has(file.path)) next.delete(file.path);
                    else next.add(file.path);
                    return next;
                  })
                }
                onOpenAtLine={(line) => openFileAtLine(file.path, line)}
                onOpenFullDiff={() => setFullDiffFile(file)}
              />
            );
          })}
        </div>
      )}

      {/* Conflicts */}
      {conflicts.length > 0 && (
        <div className="border-t border-danger/40 bg-danger-bg px-3 py-2">
          <p className="flex items-center gap-1.5 text-xs font-medium text-danger">
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
            {t('ide.conflictsTitle')}
          </p>
          <ul className="mt-1 space-y-0.5">
            {conflicts.map((c) => (
              <li key={c.path} className="font-mono text-[11px] text-danger">
                {c.path} — {c.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      {(canApply || canReject) && (
        <div className="flex items-center justify-end gap-2 border-t border-border px-3 py-2">
          {canReject && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => reject.mutate()}
              loading={reject.isPending}
            >
              {t('ide.rejectAll')}
            </Button>
          )}
          {canApply && (
            <Button
              size="sm"
              onClick={() => apply.mutate()}
              disabled={selectedPaths.length === 0}
              loading={apply.isPending}
            >
              {allSelected
                ? t('ide.applyAll')
                : t('ide.applySelected', { k: selectedPaths.length, n: files.length })}
            </Button>
          )}
        </div>
      )}

      {/* Full-diff Monaco takeover */}
      <Dialog open={fullDiffFile != null} onOpenChange={(open) => !open && setFullDiffFile(null)}>
        <DialogContent size="lg" className="max-w-4xl">
          <DialogHeader>
            <DialogTitle className="truncate font-mono text-sm">{fullDiffFile?.path}</DialogTitle>
            <DialogClose />
          </DialogHeader>
          {fullDiffFile && fullDiffModel && (
            <div className="h-[70vh] border-t border-border">
              <ThemedMonacoDiff
                height="100%"
                language={languageForPath(fullDiffFile.path)}
                original={fullDiffModel.base}
                modified={fullDiffModel.modified}
              />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
