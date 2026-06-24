'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { applyPatch, listPatches, rejectPatch, type ApplyResult, type Page, type Patch } from '@/lib/api/patches';
import { Skeleton } from '@/components/ui/skeleton';

import { PatchDiff } from './PatchDiff';

export function PatchReviewPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<ApplyResult | null>(null);

  const patches = useQuery<Page<Patch>>({ queryKey: ['patches', projectId], queryFn: () => listPatches(projectId), refetchInterval: 5000 });
  const invalidate = () => { queryClient.invalidateQueries({ queryKey: ['patches', projectId] }); queryClient.invalidateQueries({ queryKey: ['workspace-tree', projectId] }); queryClient.invalidateQueries({ queryKey: ['file', projectId] }); };
  const apply = useMutation({ mutationFn: (id: string) => applyPatch(projectId, id), onSuccess: (res) => { setResult(res); invalidate(); } });
  const reject = useMutation({ mutationFn: (id: string) => rejectPatch(projectId, id), onSuccess: invalidate });
  const selectedPatch = patches.data?.items.find((p) => p.id === selected);

  const statusStyle: Record<string, string> = { pending: 'bg-amber-100 text-amber-700', applied: 'bg-emerald-100 text-emerald-700', rejected: 'bg-neutral-200 text-neutral-500', conflict: 'bg-red-100 text-red-700' };

  return (
    <div className="flex h-full flex-col">
      <h3 className="border-b border-neutral-200 px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-neutral-400">Patch proposals</h3>
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {patches.isLoading && <Skeleton className="h-12 w-full" />}
        {patches.data?.items.length === 0 && <p className="p-2 text-xs text-neutral-400">No patches yet.</p>}
        {patches.data?.items.map((patch) => (
          <div key={patch.id} className="rounded-lg border border-neutral-200 bg-white">
            <button className="flex w-full items-center justify-between px-3 py-2 text-left" onClick={() => { setSelected(patch.id === selected ? null : patch.id); setResult(null); }}>
              <span className="truncate text-xs font-medium text-neutral-800">{patch.summary || '(no summary)'}</span>
              <span className={`ml-2 rounded-full px-2 py-0.5 text-[10px] font-medium ${statusStyle[patch.status] ?? ''}`}>{patch.status}</span>
            </button>
            {selected === patch.id && selectedPatch && (
              <div className="border-t border-neutral-100 px-3 py-2 space-y-2">
                {selectedPatch.files.map((f) => <PatchDiff key={f.id} projectId={projectId} file={f} />)}
                {result?.status === 'conflict' && (
                  <div className="rounded-lg bg-red-50 p-2 text-xs text-red-700">Conflict — nothing was written:<ul className="ml-4 mt-1 list-disc">{result.conflicts.map((c) => <li key={c.path}>{c.path}: {c.reason}</li>)}</ul></div>
                )}
                {patch.status === 'pending' && (
                  <div className="flex gap-2">
                    <button onClick={() => apply.mutate(patch.id)} disabled={apply.isPending} className="rounded-lg bg-neutral-900 px-3 py-1.5 text-[11px] font-medium text-white hover:bg-neutral-800 disabled:opacity-40">Apply</button>
                    <button onClick={() => reject.mutate(patch.id)} disabled={reject.isPending} className="rounded-lg border border-neutral-300 bg-white px-3 py-1.5 text-[11px] font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-40">Reject</button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
