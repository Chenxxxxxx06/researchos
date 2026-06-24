'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { importPapers, searchPapers, type PaperResult } from '@/lib/api/research';
import { Button } from '@/components/ui/button';

export function PaperSearchPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PaperResult[]>([]);

  const search = useMutation({
    mutationFn: () => searchPapers(projectId, query, 10),
    onSuccess: (res) => setResults(res.results),
  });

  const importOne = useMutation({
    mutationFn: (paper: PaperResult) => importPapers(projectId, [paper]),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['papers', projectId] }),
  });

  return (
    <div className="space-y-3">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim()) search.mutate();
        }}
      >
        <input
          className="h-9 flex-1 rounded-md border border-neutral-300 px-2 text-sm"
          placeholder="Search arXiv…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Button size="sm" type="submit" disabled={search.isPending}>
          Search
        </Button>
      </form>

      {search.isError && <p className="text-xs text-red-600">Search failed.</p>}
      {search.isSuccess && results.length === 0 && (
        <p className="text-xs text-neutral-500">No results.</p>
      )}

      <ul className="space-y-2">
        {results.map((paper) => (
          <li key={`${paper.source}:${paper.external_id}`} className="rounded border border-neutral-200 p-2">
            <a
              href={paper.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-medium text-neutral-900 underline"
            >
              {paper.title}
            </a>
            <p className="mt-0.5 line-clamp-2 text-xs text-neutral-500">
              {paper.authors.join(', ')} · {paper.source}:{paper.external_id}
            </p>
            <Button
              size="sm"
              variant="secondary"
              className="mt-1"
              onClick={() => importOne.mutate(paper)}
              disabled={importOne.isPending}
            >
              Add to library
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
