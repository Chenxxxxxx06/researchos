'use client';

/**
 * Inline revert confirm (D5) — no modal dependency. Revert is non-destructive
 * (an inverse commit). 409 `git_dirty` / `git_revert_conflict` render inline.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Undo2 } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { ApiError } from '@/lib/api/client';
import { revertCommit } from '@/lib/api/git';
import { useIdeStore } from '@/lib/ide/store';
import { useI18n } from '@/lib/i18n';

export function RevertRow({ projectId, sha }: { projectId: string; sha: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const selectCommit = useIdeStore((s) => s.selectCommit);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const revert = useMutation({
    mutationFn: () => revertCommit(projectId, sha),
    onSuccess: (result) => {
      setConfirming(false);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ['git-log', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['git-status', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['workspace-tree', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['file', projectId] });
      selectCommit(result.commit_sha);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'git_dirty') setError(t('ide.revertTreeDirty'));
      else if (err instanceof ApiError && err.code === 'git_revert_conflict') setError(t('ide.revertConflict'));
      else setError(err instanceof Error ? err.message : t('ide.revertFailed'));
    },
  });

  if (!confirming) {
    return (
      <Button variant="outline" size="sm" onClick={() => setConfirming(true)}>
        <Undo2 className="h-3.5 w-3.5" aria-hidden="true" />
        {t('ide.revert')}
      </Button>
    );
  }

  return (
    <div className="w-full space-y-2 rounded-md border border-warn/40 bg-warn-bg p-2">
      <p className="flex items-start gap-1.5 text-xs text-warn">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        {t('ide.revertConfirm')}
      </p>
      {error && <p className="text-xs text-danger">{error}</p>}
      <div className="flex gap-2">
        <Button size="sm" loading={revert.isPending} onClick={() => revert.mutate()}>
          {t('ide.revert')}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setConfirming(false);
            setError(null);
          }}
        >
          {t('common.cancel')}
        </Button>
      </div>
    </div>
  );
}
