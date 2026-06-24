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

  const importAll = useMutation({
    mutationFn: () => importPapers(projectId, results),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['papers', projectId] });
      setResults([]);
    },
  });

  const importOne = useMutation({
    mutationFn: (paper: PaperResult) => importPapers(projectId, [paper]),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['papers', projectId] }),
  });

  return (
    <div className="flex h-full flex-col">
      <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-neutral-400">Find papers</h3>
      <form className="mb-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (query.trim()) search.mutate(); }}>
        <input className="h-9 flex-1 rounded-lg border border-neutral-300 bg-neutral-50 px-3 text-xs placeholder:text-neutral-400" placeholder="Search arXiv…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <Button size="sm" type="submit" disabled={search.isPending}>Search</Button>
      </form>

      {search.isPending && <p className="text-xs text-neutral-400">Searching…</p>}
      {search.isError && <p className="text-xs text-red-600">Search failed.</p>}
      {results.length > 0 && (
        <Button size="sm" variant="secondary" className="mb-2 w-full" disabled={importAll.isPending} onClick={() => importAll.mutate()}>
          Import all ({results.length})
        </Button>
      )}

      <div className="flex-1 space-y-2 overflow-y-auto">
        {results.map((paper) => (
          <div key={`${paper.source}:${paper.external_id}`} className="rounded-lg border border-neutral-200 bg-white p-3 shadow-sm">
            <a href={paper.url} target="_blank" rel="noreferrer" className="text-xs font-semibold leading-snug text-neutral-900 hover:underline">{paper.title}</a>
            <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-neutral-400">{(paper.abstract ?? '').slice(0, 160) || paper.authors.join(', ')}</p>
            <div className="mt-2 flex items-center justify-between">
              <span className="rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[10px] text-neutral-500">{paper.source}:{paper.external_id}</span>
              <Button size="sm" variant="secondary" className="h-7 text-[11px]" onClick={() => importOne.mutate(paper)} disabled={importOne.isPending}>+ Library</Button>
            </div>
          </div>
        ))}
        {search.isSuccess && results.length === 0 && <p className="text-xs text-neutral-400">No results.</p>}
      </div>
    </div>
  );
}
