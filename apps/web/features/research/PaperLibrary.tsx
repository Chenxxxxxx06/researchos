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
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Library
      </h3>
      {isLoading && <Skeleton className="h-16 w-full" />}
      {isError && <p className="text-xs text-red-600">Failed to load.</p>}
      {data && data.items.length === 0 && (
        <p className="text-xs text-neutral-500">No papers yet. Search to add some.</p>
      )}
      <ul className="space-y-1">
        {data?.items.map((paper) => (
          <li key={paper.id} className="rounded border border-neutral-200 p-2">
            <a
              href={paper.url}
              target="_blank"
              rel="noreferrer"
              className="text-xs font-medium text-neutral-800 underline"
            >
              {paper.title}
            </a>
            <p className="mt-0.5 font-mono text-[10px] text-neutral-400">
              {paper.source}:{paper.external_id}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
