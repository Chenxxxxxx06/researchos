'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, ChevronDown, Sparkles, Wand2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { listCritiques, runCriticReview, updateIdea, type Critique, type Idea } from '@/lib/api/ideas';
import { useI18n, type DictKey } from '@/lib/i18n';
import type { LiveRun } from '@/lib/websocket/useProjectAgentEvents';
import { Badge, type BadgeProps } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import { CitationChip } from '../CitationChip';
import { useChatSeedStore } from '../chatSeed';
import { resolveCitation, type LibraryMap } from '../citations';
import { CriticReviewCard } from './CriticReviewCard';

const GAP_META: Record<string, { key: DictKey; variant: BadgeProps['variant'] }> = {
  coverage: { key: 'research.ideas.gapCoverage', variant: 'info' },
  limitation: { key: 'research.ideas.gapLimitation', variant: 'warn' },
  transfer: { key: 'research.ideas.gapTransfer', variant: 'accent' },
};

/**
 * Gap-typed idea card (D8.2): gap badge, novelty pill, expandable body with
 * cited-support chips linking into the Reading Room, critic flow driven by the
 * shared run status (no count-polling), and the "Develop this idea" chat handoff.
 */
export function IdeaCard({
  projectId,
  idea,
  runs,
  trackRun,
  library,
}: {
  projectId: string;
  idea: Idea;
  runs: Record<string, LiveRun>;
  trackRun: (runId: string) => void;
  library: LibraryMap;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const setSeed = useChatSeedStore((s) => s.setSeed);

  const [expanded, setExpanded] = useState(false);
  const [criticRunId, setCriticRunId] = useState<string | null>(null);
  const [criticError, setCriticError] = useState<string | null>(null);

  const criticRun = criticRunId ? runs[criticRunId] : undefined;
  const reviewing = criticRunId !== null;

  const gapType = idea.metadata.gap_type ?? null;
  const gapMeta = gapType ? (GAP_META[gapType] ?? { key: 'research.ideas.gapOther' as DictKey, variant: 'neutral' as const }) : null;
  const supportKeys = idea.metadata.supporting_paper_keys ?? [];

  const critiques = useQuery<Critique[]>({
    queryKey: ['critiques', projectId, idea.id],
    queryFn: () => listCritiques(projectId, idea.id),
    enabled: expanded,
    // No-WS fallback ONLY while a critic run is in flight (D8.3); completion is
    // detected from the shared run status below, never from critique count growth.
    refetchInterval: criticRunId ? 5000 : false,
  });

  const review = useMutation({
    mutationFn: () => runCriticReview(projectId, idea.id),
    onSuccess: (res) => {
      setCriticError(null);
      setCriticRunId(res.agent_run_id);
      trackRun(res.agent_run_id);
    },
  });

  const archive = useMutation({
    mutationFn: () => updateIdea(projectId, idea.id, { status: 'archived' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ideas', projectId] }),
  });

  // Critic completion via the shared run status (D8.3) — no count-growth polling.
  useEffect(() => {
    if (!criticRun) return;
    if (criticRun.status === 'completed') {
      queryClient.invalidateQueries({ queryKey: ['critiques', projectId, idea.id] });
      setCriticRunId(null);
    } else if (criticRun.status === 'failed' || criticRun.status === 'cancelled') {
      setCriticError(criticRun.error ?? t('research.critic.failed'));
      setCriticRunId(null);
    }
  }, [criticRun, projectId, idea.id, queryClient, t]);

  return (
    <div className="rounded-lg border border-border bg-surface">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="w-full px-3 py-2 text-left"
      >
        <div className="flex items-start justify-between gap-2">
          <span className="text-xs font-medium leading-snug text-text">{idea.title}</span>
          <ChevronDown
            className={cn('h-3.5 w-3.5 shrink-0 text-muted transition-transform', expanded && 'rotate-180')}
            aria-hidden="true"
          />
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1">
          {gapMeta && (
            <Badge variant={gapMeta.variant} size="sm">
              {t(gapMeta.key)}
            </Badge>
          )}
          {idea.novelty_score != null && (
            <Badge variant="neutral" size="sm">
              {t('research.ideas.novelty', { score: idea.novelty_score.toFixed(2) })}
            </Badge>
          )}
          {idea.status === 'archived' && (
            <Badge variant="outline" size="sm">
              {t('research.ideas.archived')}
            </Badge>
          )}
        </div>
      </button>

      {expanded && (
        <div className="space-y-2.5 border-t border-border px-3 py-2.5">
          {idea.description && <p className="text-xs leading-relaxed text-muted">{idea.description}</p>}

          {idea.hypothesis && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">
                {t('research.ideas.hypothesis')}
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-muted">{idea.hypothesis}</p>
            </div>
          )}

          {supportKeys.length > 0 && (
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-faint">
                {t('research.ideas.support')}
              </p>
              <div className="flex flex-wrap gap-1">
                {supportKeys.map((key) => (
                  <CitationChip key={key} projectId={projectId} model={resolveCitation(key, [], library)} />
                ))}
              </div>
            </div>
          )}

          {critiques.data?.map((c) => (
            <CriticReviewCard key={c.id} critique={c} projectId={projectId} library={library} />
          ))}
          {criticError && <p className="text-[11px] text-danger">{criticError}</p>}

          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
            <Button
              size="sm"
              variant="secondary"
              className="h-7 text-[11px]"
              loading={reviewing}
              disabled={reviewing}
              onClick={() => review.mutate()}
            >
              <Sparkles className="h-3 w-3" aria-hidden="true" />
              {reviewing ? t('research.ideas.reviewing') : t('research.ideas.runCritic')}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-[11px]"
              onClick={() => setSeed({ kind: 'idea', ideaId: idea.id, ideaTitle: idea.title })}
            >
              <Wand2 className="h-3 w-3" aria-hidden="true" />
              {t('research.ideas.develop')}
            </Button>
            {idea.status !== 'archived' && (
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-[11px]"
                loading={archive.isPending}
                onClick={() => archive.mutate()}
              >
                <Archive className="h-3 w-3" aria-hidden="true" />
                {t('research.ideas.archive')}
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
