'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  applyPatch,
  listPatches,
  rejectPatch,
  type ApplyResult,
  type Page,
  type Patch,
} from '@/lib/api/patches';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

import { PatchDiff } from './PatchDiff';

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700',
  applied: 'bg-green-100 text-green-700',
  rejected: 'bg-neutral-200 text-neutral-600',
  conflict: 'bg-red-100 text-red-700',
};

export function PatchReviewPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<ApplyResult | null>(null);

  const patches = useQuery<Page<Patch>>({
    queryKey: ['patches', projectId],
    queryFn: () => listPatches(projectId),
    refetchInterval: 4000,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['patches', projectId] });
    queryClient.invalidateQueries({ queryKey: ['workspace-tree', projectId] });
    queryClient.invalidateQueries({ queryKey: ['file', projectId] });
  };

  const apply = useMutation({
    mutationFn: (id: string) => applyPatch(projectId, id),
    onSuccess: (res) => {
      setResult(res);
      invalidate();
    },
  });
  const reject = useMutation({
    mutationFn: (id: string) => rejectPatch(projectId, id),
    onSuccess: invalidate,
  });

  const selectedPatch = patches.data?.items.find((p) => p.id === selected);

  return (
    <div className="flex h-full flex-col">
      <h3 className="border-b border-neutral-200 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Patch proposals
      </h3>

      <div className="flex-1 overflow-y-auto p-2">
        {patches.isLoading && <Skeleton className="h-16 w-full" />}
        {patches.data && patches.data.items.length === 0 && (
          <p className="px-1 text-xs text-neutral-400">No patches yet.</p>
        )}

        <ul className="space-y-1">
          {patches.data?.items.map((patch) => (
            <li key={patch.id} className="rounded border border-neutral-200 p-2">
              <button
                className="flex w-full items-center justify-between text-left"
                onClick={() => {
                  setSelected(patch.id === selected ? null : patch.id);
                  setResult(null);
                }}
              >
                <span className="truncate text-xs font-medium text-neutral-800">
                  {patch.summary || '(no summary)'}
                </span>
                <span
                  className={`ml-2 rounded px-1.5 text-[10px] ${STATUS_COLORS[patch.status] ?? ''}`}
                >
                  {patch.status}
                </span>
              </button>

              {selected === patch.id && selectedPatch && (
                <div className="mt-2 space-y-2">
                  {selectedPatch.files.map((file) => (
                    <PatchDiff key={file.id} projectId={projectId} file={file} />
                  ))}

                  {result?.status === 'conflict' && (
                    <div className="rounded bg-red-50 p-2 text-xs text-red-700">
                      Conflict — nothing was written:
                      <ul className="ml-4 list-disc">
                        {result.conflicts.map((c) => (
                          <li key={c.path}>
                            {c.path}: {c.reason}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {patch.status === 'pending' && (
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        disabled={apply.isPending}
                        onClick={() => apply.mutate(patch.id)}
                      >
                        Apply
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={reject.isPending}
                        onClick={() => reject.mutate(patch.id)}
                      >
                        Reject
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
