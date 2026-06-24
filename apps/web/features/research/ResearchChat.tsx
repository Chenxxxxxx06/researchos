'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import { createAgentRun, listAgentRuns, type AgentRun, type Page } from '@/lib/api/agents';
import { ApiError } from '@/lib/api/client';
import { listLLMConfigs } from '@/lib/api/llmConfig';
import { useI18n } from '@/lib/i18n';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';
import { Skeleton } from '@/components/ui/skeleton';

import { AgentRunMessage } from './AgentRunMessage';

export function ResearchChat({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const { runs, trackRun } = useProjectAgentEvents(projectId);
  const [message, setMessage] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  const llmConfigs = useQuery({ queryKey: ['llm-configs', projectId], queryFn: () => listLLMConfigs(projectId) });
  const hasRealLLM = (llmConfigs.data?.length ?? 0) > 0;

  const history = useQuery<Page<AgentRun>, ApiError>({
    queryKey: ['agent-runs', projectId],
    queryFn: () => listAgentRuns(projectId),
  });

  const mutation = useMutation({
    mutationFn: () => createAgentRun(projectId, { agent_type: 'research', message }),
    onSuccess: (res) => { trackRun(res.agent_run_id); setMessage(''); },
  });

  useEffect(() => {
    const anyDone = Object.values(runs).some((r) => r.status === 'completed' || r.status === 'failed');
    if (anyDone) queryClient.invalidateQueries({ queryKey: ['agent-runs', projectId] });
  }, [runs, projectId, queryClient]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [runs]);

  const persisted = history.data?.items ?? [];
  const persistedIds = new Set(persisted.map((r) => r.id));
  const liveOnly = Object.values(runs).filter((r) => !persistedIds.has(r.runId));
  const researchRuns = persisted.filter((r) => r.agent_type === 'research').reverse();

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-neutral-200 bg-white px-4 py-2.5">
        <h2 className="text-sm font-semibold text-neutral-800">Research Copilot</h2>
        {!hasRealLLM && (
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-medium text-amber-700">
            Mock LLM — set API key in Settings
          </span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {history.isLoading && <Skeleton className="h-20 w-full" />}
        {history.isError && <p className="text-sm text-red-600">Failed to load.</p>}

        {!history.isLoading && researchRuns.length === 0 && liveOnly.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <span className="text-3xl">🔍</span>
            <p className="mt-3 text-sm font-medium text-neutral-700">Ask a research question</p>
            <p className="mt-1 text-xs text-neutral-400 max-w-xs">
              E.g. &ldquo;What are the latest methods for vision-language pretraining?&rdquo;
            </p>
          </div>
        )}

        {researchRuns.map((run) => (
          <div key={run.id} className="space-y-3">
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-neutral-900 px-4 py-2.5 text-sm leading-relaxed text-white">
                {run.input_json.message}
              </div>
            </div>
            <div className="flex justify-start">
              <div className="max-w-[90%] rounded-2xl rounded-bl-md border border-neutral-200 bg-white px-4 py-3 text-sm leading-relaxed text-neutral-800 shadow-sm">
                {run.output_json?.message ?? `(${run.status})`}
                {(run.output_json?.citations ?? []).length > 0 && (
                  <div className="mt-2 border-t border-neutral-100 pt-2">
                    <p className="mb-1 text-[11px] font-medium text-neutral-400">SOURCES</p>
                    <div className="flex flex-wrap gap-1">
                      {(run.output_json?.citations ?? []).map((key) => (
                        <span key={key} className="rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[10px] text-neutral-600">{key}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {liveOnly.map((run) => (
          <AgentRunMessage key={run.runId} run={run} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form className="flex gap-2 border-t border-neutral-200 bg-white px-4 py-3" onSubmit={(e) => { e.preventDefault(); if (message.trim()) mutation.mutate(); }}>
        <input
          className="h-10 flex-1 rounded-xl border border-neutral-300 bg-neutral-50 px-4 text-sm placeholder:text-neutral-400 focus:border-neutral-500 focus:outline-none"
          placeholder="Ask about recent papers, methods, datasets…"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={mutation.isPending}
        />
        <button
          type="submit"
          disabled={mutation.isPending || !message.trim()}
          className="h-10 rounded-xl bg-neutral-900 px-5 text-sm font-medium text-white transition-colors hover:bg-neutral-800 disabled:opacity-40"
        >
          {mutation.isPending ? '…' : '→'}
        </button>
      </form>
    </div>
  );
}
