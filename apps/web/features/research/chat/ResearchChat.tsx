'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Send } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import {
  createAgentRun,
  listAgentRuns,
  type AgentRun,
  type AgentRunContext,
  type CreateAgentRunResponse,
  type Page,
} from '@/lib/api/agents';
import { ApiError } from '@/lib/api/client';
import { citationKey, listPapers } from '@/lib/api/papers';
import { listIdeas } from '@/lib/api/ideas';
import { listLLMConfigs } from '@/lib/api/llmConfig';
import { useI18n, type DictKey } from '@/lib/i18n';
import type { LiveRun } from '@/lib/websocket/useProjectAgentEvents';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';

import { CitationChip } from '../CitationChip';
import type { ChatSeed } from '../chatSeed';
import { useChatSeedStore } from '../chatSeed';
import { resolveCitation, useCitationResolver } from '../citations';
import { AgentRunMessage } from './AgentRunMessage';
import { ContextBanner } from './ContextBanner';
import { buildSuggestions, type Suggestion } from './suggestions';
import { SuggestionChips } from './SuggestionChips';

const PAGE = 20;

const TEMPLATE_KEY: Record<ChatSeed['kind'], DictKey> = {
  section: 'research.chat.templateSection',
  paper: 'research.chat.templatePaper',
  idea: 'research.chat.templateIdea',
  gap: 'research.chat.templateGap',
};

/** Map a seed + message into the `createAgentRun` body (D6 table). */
function seedToRequest(
  message: string,
  seed: ChatSeed | null,
): { message: string; context?: AgentRunContext } {
  if (!seed) return { message };
  switch (seed.kind) {
    case 'section':
      return { message, context: { paper_id: seed.paperId, section_seqs: [seed.sectionSeq] } };
    case 'paper':
      return { message, context: { paper_id: seed.paperId } };
    case 'idea':
      return { message, context: { idea_id: seed.ideaId } };
    case 'gap':
      return {
        message: `${message}\n\nGap context: method "${seed.method}" has not been applied to problem "${seed.problem}". Supporting papers: ${seed.paperKeys.join(', ')}`,
      };
  }
}

interface Pending {
  message: string;
  seed: ChatSeed | null;
}

/**
 * Research chat column (D6/D7). Consumes the shared `runs`/`trackRun` from the
 * workspace; renders persisted research runs plus live bubbles for runs THIS
 * chat started (tracked via `pendingPrompts`) — so critic/other runs sharing the
 * socket never bleed in. Seed context drives a banner, a template prefill and the
 * run `context`.
 */
export function ResearchChat({
  projectId,
  runs,
  trackRun,
  onFocusDiscover,
}: {
  projectId: string;
  runs: Record<string, LiveRun>;
  trackRun: (runId: string) => void;
  onFocusDiscover?: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const library = useCitationResolver(projectId);

  const seed = useChatSeedStore((s) => s.seed);
  const setSeed = useChatSeedStore((s) => s.setSeed);
  const clearSeed = useChatSeedStore((s) => s.clear);

  const [message, setMessage] = useState('');
  const [pendingPrompts, setPendingPrompts] = useState<Record<string, Pending>>({});
  const [older, setOlder] = useState<AgentRun[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastSeedRef = useRef<ChatSeed | null>(null);

  const llm = useQuery({ queryKey: ['llm-configs', projectId], queryFn: () => listLLMConfigs(projectId) });
  const hasRealLLM = (llm.data?.length ?? 0) > 0;

  const history = useQuery<Page<AgentRun>, ApiError>({
    queryKey: ['agent-runs', projectId],
    queryFn: () => listAgentRuns(projectId, { limit: PAGE }),
  });

  const papersQ = useQuery({ queryKey: ['papers', projectId], queryFn: () => listPapers(projectId, { limit: 100 }) });
  const ideasQ = useQuery({ queryKey: ['ideas', projectId], queryFn: () => listIdeas(projectId, { limit: 50 }) });
  const suggestions = useMemo(
    () => buildSuggestions(papersQ.data?.items ?? [], ideasQ.data?.items ?? [], t),
    [papersQ.data, ideasQ.data, t],
  );

  // Template prefill when a fresh seed arrives.
  useEffect(() => {
    if (seed && seed !== lastSeedRef.current) {
      setMessage(t(TEMPLATE_KEY[seed.kind]));
      lastSeedRef.current = seed;
    }
    if (!seed) lastSeedRef.current = null;
  }, [seed, t]);

  const mutation = useMutation<CreateAgentRunResponse, ApiError, Pending>({
    mutationFn: ({ message: msg, seed: s }) => {
      const body = seedToRequest(msg, s);
      return createAgentRun(projectId, { agent_type: 'research', message: body.message, context: body.context });
    },
    onSuccess: (res, vars) => {
      setPendingPrompts((prev) => ({ ...prev, [res.agent_run_id]: vars }));
      trackRun(res.agent_run_id);
      setMessage('');
      clearSeed();
      lastSeedRef.current = null;
    },
  });

  const loadEarlier = useMutation({
    mutationFn: () =>
      listAgentRuns(projectId, { limit: PAGE, offset: (history.data?.items.length ?? 0) + older.length }),
    onSuccess: (page) => setOlder((prev) => [...prev, ...page.items]),
  });

  // Refetch persisted history when one of OUR runs terminates (self-heals token loss).
  useEffect(() => {
    const done = Object.keys(pendingPrompts).some(
      (id) => runs[id] && (runs[id].status === 'completed' || runs[id].status === 'failed'),
    );
    if (done) queryClient.invalidateQueries({ queryKey: ['agent-runs', projectId] });
  }, [runs, pendingPrompts, projectId, queryClient]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [runs, history.data]);

  const persisted = useMemo(
    () => [...(history.data?.items ?? []), ...older],
    [history.data, older],
  );
  const persistedById = useMemo(() => new Map(persisted.map((r) => [r.id, r])), [persisted]);
  const isSettled = (id: string) => Boolean(persistedById.get(id)?.output_json);

  const researchRuns = persisted
    .filter((r) => r.agent_type === 'research')
    .filter((r) => !pendingPrompts[r.id] || isSettled(r.id))
    .reverse();

  const liveOnly = Object.keys(pendingPrompts)
    .filter((id) => !isSettled(id) && runs[id])
    .map((id) => ({ run: runs[id], prompt: pendingPrompts[id].message }));

  const loadedCount = (history.data?.items.length ?? 0) + older.length;
  const hasEarlier = loadedCount < (history.data?.total ?? 0);
  const isEmpty = !history.isLoading && researchRuns.length === 0 && liveOnly.length === 0;

  const submit = () => {
    const text = message.trim();
    if (!text || mutation.isPending) return;
    mutation.mutate({ message: text, seed });
  };

  const onSuggestion = (s: Suggestion) => {
    const a = s.action;
    if (a.type === 'focus-discover') onFocusDiscover?.();
    else if (a.type === 'message') setMessage(a.message);
    else setSeed(a.seed);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-2.5">
        <h2 className="text-sm font-semibold text-text">{t('research.chat.title')}</h2>
        {!hasRealLLM && (
          <Badge variant="warn" size="sm">
            {t('research.chat.mockBadge')}
          </Badge>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {history.isLoading && <Skeleton className="h-20 w-full" />}
        {history.isError && (
          <div className="rounded-md bg-danger-bg px-3 py-2 text-xs text-danger">
            <p>{t('research.chat.failed')}</p>
            <Button size="sm" variant="ghost" className="mt-1 h-7 text-[11px]" onClick={() => history.refetch()}>
              {t('research.common.retry')}
            </Button>
          </div>
        )}

        {hasEarlier && !isEmpty && (
          <div className="flex justify-center">
            <Button size="sm" variant="ghost" className="h-7 text-[11px]" loading={loadEarlier.isPending} onClick={() => loadEarlier.mutate()}>
              {t('research.chat.loadEarlier')}
            </Button>
          </div>
        )}

        {isEmpty && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <span className="text-2xl">🔍</span>
            <div>
              <p className="text-sm font-medium text-text">{t('research.chat.emptyTitle')}</p>
              <p className="mt-1 max-w-xs text-xs text-muted">{t('research.chat.emptyBody')}</p>
            </div>
            <SuggestionChips suggestions={suggestions} onSelect={onSuggestion} />
          </div>
        )}

        {researchRuns.map((run) => (
          <div key={run.id} className="space-y-3">
            <div className="flex justify-end">
              <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-sm leading-relaxed text-accent-fg">
                {run.input_json.message}
              </div>
            </div>
            <div className="flex justify-start">
              <div className="max-w-[90%] rounded-2xl rounded-bl-md border border-border bg-surface px-4 py-3 text-sm leading-relaxed text-text shadow-elev1">
                {run.output_json?.message ? (
                  <p className="whitespace-pre-wrap">{run.output_json.message}</p>
                ) : (
                  <span className="text-muted">({run.status})</span>
                )}
                {(run.output_json?.citations ?? []).length > 0 && (
                  <div className="mt-2 border-t border-border pt-2">
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-faint">
                      {t('research.chat.sources')}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {(run.output_json?.citations ?? []).map((key) => (
                        <CitationChip key={key} projectId={projectId} model={resolveCitation(key, [], library)} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {liveOnly.map(({ run, prompt }) => (
          <AgentRunMessage key={run.runId} run={run} prompt={prompt} projectId={projectId} library={library} />
        ))}

        <div ref={bottomRef} />
      </div>

      <div className="space-y-2 border-t border-border bg-surface px-4 py-3">
        {seed && <ContextBanner seed={seed} onClear={clearSeed} />}
        {!isEmpty && !message.trim() && suggestions.length > 0 && (
          <SuggestionChips suggestions={suggestions} onSelect={onSuggestion} />
        )}
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={t('research.chat.placeholder')}
            disabled={mutation.isPending}
            aria-label={t('research.chat.placeholder')}
          />
          <Button type="submit" className="shrink-0" loading={mutation.isPending} disabled={!message.trim()}>
            <Send className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">{t('research.chat.send')}</span>
          </Button>
        </form>
      </div>
    </div>
  );
}
