'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import {
  createIdea,
  listCritiques,
  listIdeas,
  runCriticReview,
  type Critique,
  type Idea,
  type Page,
} from '@/lib/api/research';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

import { CriticReviewCard } from './CriticReviewCard';

export function IdeaPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const baselineCount = useRef(0);

  const ideas = useQuery<Page<Idea>>({
    queryKey: ['ideas', projectId],
    queryFn: () => listIdeas(projectId),
  });

  const critiques = useQuery<Critique[]>({
    queryKey: ['critiques', projectId, selectedId],
    queryFn: () => listCritiques(projectId, selectedId!),
    enabled: Boolean(selectedId),
    refetchInterval: reviewing ? 1500 : false,
  });

  // Stop polling once a new critique lands.
  useEffect(() => {
    if (reviewing && critiques.data && critiques.data.length > baselineCount.current) {
      setReviewing(false);
    }
  }, [reviewing, critiques.data]);

  const create = useMutation({
    mutationFn: () => createIdea(projectId, { title }),
    onSuccess: () => {
      setTitle('');
      queryClient.invalidateQueries({ queryKey: ['ideas', projectId] });
    },
  });

  const review = useMutation({
    mutationFn: (ideaId: string) => runCriticReview(projectId, ideaId),
    onSuccess: () => {
      baselineCount.current = critiques.data?.length ?? 0;
      setReviewing(true);
    },
  });

  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Ideas
      </h3>
      <form
        className="mb-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) create.mutate();
        }}
      >
        <Input
          className="h-9"
          placeholder="New idea title…"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <Button size="sm" type="submit" disabled={create.isPending}>
          Add
        </Button>
      </form>

      {ideas.data && ideas.data.items.length === 0 && (
        <p className="text-xs text-neutral-500">No ideas yet.</p>
      )}

      <ul className="space-y-1">
        {ideas.data?.items.map((idea) => (
          <li key={idea.id} className="rounded border border-neutral-200 p-2">
            <button
              className="text-left text-sm font-medium text-neutral-800"
              onClick={() => setSelectedId(idea.id === selectedId ? null : idea.id)}
            >
              {idea.title}
            </button>
            {selectedId === idea.id && (
              <div className="mt-2 space-y-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={review.isPending || reviewing}
                  onClick={() => review.mutate(idea.id)}
                >
                  {reviewing ? 'Reviewing…' : 'Run critic review'}
                </Button>
                {critiques.data?.map((c) => (
                  <CriticReviewCard key={c.id} critique={c} />
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
