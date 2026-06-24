'use client';

import { useQuery } from '@tanstack/react-query';

import { listPapers, type Page, type Paper } from '@/lib/api/research';
import { ApiError } from '@/lib/api/client';
import { Skeleton } from '@/components/ui/skeleton';

export function PaperLibrary({ projectId }: { projectId: string }) {
  const { data, isLoading, isError } = useQuery<Page<Paper>, ApiError>({
    queryKey: ['papers', projectId],
    queryFn: () => listPapers(projectId),
  });

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400">Library</h3>
        {data && <span className="rounded-full bg-neutral-100 px-1.5 text-[10px] font-medium text-neutral-500">{data.total}</span>}
      </div>
      {isLoading && <Skeleton className="h-12 w-full" />}
      {isError && <p className="text-[11px] text-red-600">Failed to load.</p>}
      {data?.items.length === 0 && <p className="text-[11px] text-neutral-400">No papers yet.</p>}
      <ul className="space-y-1">
        {data?.items.map((paper) => (
          <li key={paper.id}>
            <a href={paper.url} target="_blank" rel="noreferrer" className="block rounded-md px-2 py-1.5 text-xs leading-snug text-neutral-700 hover:bg-neutral-100">
              <span className="font-medium">{paper.title}</span>
              <span className="ml-1.5 font-mono text-[10px] text-neutral-400">{paper.source}:{paper.external_id}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
