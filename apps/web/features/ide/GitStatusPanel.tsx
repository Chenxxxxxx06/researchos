'use client';

import { useQuery } from '@tanstack/react-query';

import { getGitStatus, type GitStatus } from '@/lib/api/git';

export function GitStatusPanel({ projectId }: { projectId: string }) {
  const { data } = useQuery<GitStatus>({
    queryKey: ['git-status', projectId],
    queryFn: () => getGitStatus(projectId),
  });

  return (
    <div className="border-t border-neutral-200 px-2 py-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Source control
      </h3>
      {data ? (
        <p className="mt-1 text-xs text-neutral-600">
          <span className="font-mono">{data.branch}</span> ·{' '}
          {data.clean ? 'clean' : `${data.files.length} changed`}
          <span className="ml-1 text-neutral-400">({data.provider})</span>
        </p>
      ) : (
        <p className="mt-1 text-xs text-neutral-400">…</p>
      )}
    </div>
  );
}
