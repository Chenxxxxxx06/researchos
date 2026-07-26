'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Lightbulb, Sparkles } from 'lucide-react';
import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  createIdea,
  generateIdeas,
  listIdeas,
  type GenerateIdeasResponse,
  type Idea,
} from '@/lib/api/ideas';
import { listPapers, type Page as PapersPage, type Paper } from '@/lib/api/papers';
import type { Page } from '@/lib/api/agents';
import { useI18n } from '@/lib/i18n';
import type { LiveRun } from '@/lib/websocket/useProjectAgentEvents';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip } from '@/components/ui/tooltip';

import { useCitationResolver } from '../citations';
import { IdeaCard } from './IdeaCard';

const MIN_PAPERS = 5;

/**
 * Ideas panel v2 (D8). Idea generation is a SYNCHRONOUS call (CONSOLIDATION §7 —
 * no `ideate` agent, no streaming, no gap-matrix): the result replaces the list.
 * Critic completion is read from the shared run status inside each `IdeaCard`.
 */
export function IdeaPanel({
  projectId,
  runs,
  trackRun,
}: {
  projectId: string;
  runs: Record<string, LiveRun>;
  trackRun: (runId: string) => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const library = useCitationResolver(projectId);

  const [title, setTitle] = useState('');
  const [genNote, setGenNote] = useState<string | null>(null);

  const papers = useQuery<PapersPage<Paper>>({
    queryKey: ['papers', projectId],
    queryFn: () => listPapers(projectId, { limit: 100 }),
  });
  const papersTotal = papers.data?.total ?? 0;
  const canGenerate = papersTotal >= MIN_PAPERS;

  const ideas = useQuery<Page<Idea>>({
    queryKey: ['ideas', projectId],
    queryFn: () => listIdeas(projectId, { limit: 50 }),
  });

  const generate = useMutation<GenerateIdeasResponse, ApiError, void>({
    mutationFn: () => generateIdeas(projectId),
    onSuccess: (res) => {
      setGenNote(t('research.ideas.generated', { n: res.ideas.length }));
      queryClient.invalidateQueries({ queryKey: ['ideas', projectId] });
    },
    onError: (err) => {
      setGenNote(err.status === 409 ? t('research.ideas.needPapers') : t('research.ideas.generateFailed'));
    },
  });

  const create = useMutation({
    mutationFn: () => createIdea(projectId, { title: title.trim() }),
    onSuccess: () => {
      setTitle('');
      queryClient.invalidateQueries({ queryKey: ['ideas', projectId] });
    },
  });

  const items = ideas.data?.items ?? [];

  const generateBtn = (
    <Button
      size="sm"
      className="w-full"
      loading={generate.isPending}
      disabled={!canGenerate || generate.isPending}
      onClick={() => generate.mutate()}
    >
      <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
      {generate.isPending ? t('research.ideas.generating') : t('research.ideas.generate')}
    </Button>
  );

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-faint">{t('research.ideas.title')}</h3>
        {ideas.data && (
          <span className="rounded-full bg-surface-2 px-1.5 text-[10px] font-medium text-muted">{ideas.data.total}</span>
        )}
      </div>

      <div className="mb-2">
        {canGenerate ? generateBtn : <Tooltip content={t('research.ideas.needPapers')}>{generateBtn}</Tooltip>}
        {genNote && <p className="mt-1 text-[11px] text-muted">{genNote}</p>}
      </div>

      <form
        className="mb-2 flex gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) create.mutate();
        }}
      >
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t('research.ideas.new')}
          className="h-8 text-xs"
        />
        <Button size="sm" className="h-8 shrink-0 text-[11px]" type="submit" loading={create.isPending} disabled={!title.trim()}>
          +
        </Button>
      </form>

      {ideas.isLoading && <Skeleton className="h-16 w-full" />}
      {ideas.isError && (
        <div className="rounded-md bg-danger-bg px-2.5 py-1.5 text-[11px] text-danger">
          <p>{t('research.ideas.failed')}</p>
          <button type="button" className="mt-0.5 underline" onClick={() => ideas.refetch()}>
            {t('research.common.retry')}
          </button>
        </div>
      )}

      {!ideas.isLoading && items.length === 0 && (
        <EmptyState
          icon={Lightbulb}
          title={t('research.ideas.empty')}
          body={t('research.ideas.emptyBody')}
          className="border-none px-2 py-6"
        />
      )}

      <div className="space-y-1.5">
        {items.map((idea) => (
          <IdeaCard
            key={idea.id}
            projectId={projectId}
            idea={idea}
            runs={runs}
            trackRun={trackRun}
            library={library}
          />
        ))}
      </div>
    </div>
  );
}
