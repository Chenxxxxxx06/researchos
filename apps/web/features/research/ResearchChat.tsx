'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { createAgentRun, listAgentRuns, type AgentRun, type Page } from '@/lib/api/agents';
import { ApiError } from '@/lib/api/client';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

import { AgentRunMessage } from './AgentRunMessage';
import { CitationChip } from './CitationChip';

export function ResearchChat({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const { runs, trackRun } = useProjectAgentEvents(projectId);
  const [message, setMessage] = useState('');

  const history = useQuery<Page<AgentRun>, ApiError>({
    queryKey: ['agent-runs', projectId],
    queryFn: () => listAgentRuns(projectId),
  });

  const mutation = useMutation({
    mutationFn: () => createAgentRun(projectId, { agent_type: 'research', message }),
    onSuccess: (res) => {
      trackRun(res.agent_run_id);
      setMessage('');
    },
  });

  // Fold completed live runs back into the persisted history.
  useEffect(() => {
    const anyDone = Object.values(runs).some(
      (r) => r.status === 'completed' || r.status === 'failed',
    );
    if (anyDone) queryClient.invalidateQueries({ queryKey: ['agent-runs', projectId] });
  }, [runs, projectId, queryClient]);

  const persisted = history.data?.items ?? [];
  const persistedIds = new Set(persisted.map((r) => r.id));
  const liveOnly = Object.values(runs).filter((r) => !persistedIds.has(r.runId));

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto pb-4">
        {history.isLoading && <Skeleton className="h-24 w-full" />}
        {history.isError && (
          <p className="text-sm text-red-600">Failed to load conversation.</p>
        )}
        {!history.isLoading && persisted.length === 0 && liveOnly.length === 0 && (
          <p className="text-sm text-neutral-500">
            Ask a research question to search papers and get a source-backed answer.
          </p>
        )}

        {persisted
          .filter((r) => r.agent_type === 'research')
          .slice()
          .reverse()
          .map((run) => (
            <div key={run.id} className="space-y-2">
              <div className="rounded-lg bg-neutral-900 p-3 text-sm text-white">
                {run.input_json.message}
              </div>
              <div className="rounded-lg border border-neutral-200 bg-white p-3">
                <p className="whitespace-pre-wrap text-sm text-neutral-800">
                  {run.output_json?.message ?? `(${run.status})`}
                </p>
                {(run.output_json?.citations ?? []).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {(run.output_json?.citations ?? []).map((key) => (
                      <CitationChip key={key} citation={{ label: key }} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

        {liveOnly.map((run) => (
          <AgentRunMessage key={run.runId} run={run} />
        ))}
      </div>

      <form
        className="flex gap-2 border-t border-neutral-200 pt-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (message.trim()) mutation.mutate();
        }}
      >
        <input
          className="h-10 flex-1 rounded-md border border-neutral-300 px-3 text-sm"
          placeholder="Ask about recent papers, methods, datasets…"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <Button type="submit" disabled={mutation.isPending || !message.trim()}>
          {mutation.isPending ? 'Sending…' : 'Send'}
        </Button>
      </form>
    </div>
  );
}
