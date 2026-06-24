'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import { createIdea, listCritiques, listIdeas, runCriticReview, type Critique, type Idea, type Page } from '@/lib/api/research';
import { Button } from '@/components/ui/button';

import { CriticReviewCard } from './CriticReviewCard';

export function IdeaPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const baselineCount = useRef(0);

  const ideas = useQuery<Page<Idea>>({ queryKey: ['ideas', projectId], queryFn: () => listIdeas(projectId) });
  const critiques = useQuery<Critique[]>({
    queryKey: ['critiques', projectId, selectedId],
    queryFn: () => listCritiques(projectId, selectedId!),
    enabled: Boolean(selectedId),
    refetchInterval: reviewing ? 1500 : false,
  });

  useEffect(() => {
    if (reviewing && critiques.data && critiques.data.length > baselineCount.current) setReviewing(false);
  }, [reviewing, critiques.data]);

  const create = useMutation({
    mutationFn: () => createIdea(projectId, { title }),
    onSuccess: () => { setTitle(''); queryClient.invalidateQueries({ queryKey: ['ideas', projectId] }); },
  });
  const review = useMutation({
    mutationFn: (ideaId: string) => runCriticReview(projectId, ideaId),
    onSuccess: () => { baselineCount.current = critiques.data?.length ?? 0; setReviewing(true); },
  });

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400">Ideas</h3>
        {ideas.data && <span className="rounded-full bg-neutral-100 px-1.5 text-[10px] font-medium text-neutral-500">{ideas.data.total}</span>}
      </div>
      <form className="mb-2 flex gap-1.5" onSubmit={(e) => { e.preventDefault(); if (title.trim()) create.mutate(); }}>
        <input className="h-8 flex-1 rounded-lg border border-neutral-300 bg-neutral-50 px-2 text-xs placeholder:text-neutral-400" placeholder="New idea…" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Button size="sm" className="h-8 text-[11px]" type="submit" disabled={create.isPending}>+</Button>
      </form>
      {ideas.data?.items.length === 0 && <p className="text-[11px] text-neutral-400">No ideas yet.</p>}
      <ul className="space-y-1">
        {ideas.data?.items.map((idea) => (
          <li key={idea.id} className="rounded-lg border border-neutral-200 bg-white">
            <button className="w-full px-3 py-2 text-left text-xs font-medium text-neutral-800 hover:bg-neutral-50" onClick={() => setSelectedId(idea.id === selectedId ? null : idea.id)}>
              {idea.title}
              <span className="ml-1.5 rounded bg-neutral-100 px-1 text-[10px] text-neutral-400">{idea.status}</span>
            </button>
            {selectedId === idea.id && (
              <div className="border-t border-neutral-100 px-3 py-2 space-y-2">
                {idea.description && <p className="text-xs text-neutral-500">{idea.description}</p>}
                <Button size="sm" variant="secondary" className="h-7 text-[11px]" disabled={review.isPending || reviewing} onClick={() => review.mutate(idea.id)}>
                  {reviewing ? 'Reviewing…' : 'Run critic'}
                </Button>
                {critiques.data?.map((c) => <CriticReviewCard key={c.id} critique={c} />)}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
