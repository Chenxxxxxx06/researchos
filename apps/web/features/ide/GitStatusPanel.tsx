'use client';

import { useQuery } from '@tanstack/react-query';

import { getGitStatus, type GitStatus } from '@/lib/api/git';

export function GitStatusPanel({ projectId }: { projectId: string }) {
  const { data } = useQuery<GitStatus>({ queryKey: ['git-status', projectId], queryFn: () => getGitStatus(projectId) });
  return (
    <div className="border-t border-neutral-200 px-3 py-2">
      <h3 className="text-[10px] font-semibold uppercase tracking-wider text-neutral-400">Source control</h3>
      {data ? (
        <div className="mt-1 flex items-center gap-2 text-xs">
          <span className="font-mono text-neutral-700">{data.branch}</span>
          <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] text-emerald-700">{data.clean ? 'clean' : `${data.files.length} changed`}</span>
          <span className="text-neutral-400">({data.provider})</span>
        </div>
      ) : <p className="mt-1 text-xs text-neutral-400">…</p>}
    </div>
  );
}
