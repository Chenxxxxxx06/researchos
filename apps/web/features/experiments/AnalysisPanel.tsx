'use client';

import { useMutation } from '@tanstack/react-query';

import { analyzeRun } from '@/lib/api/experiments';
import { ApiError } from '@/lib/api/client';
import { useI18n } from '@/lib/i18n';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';
import { useState } from 'react';

export function AnalysisPanel({ projectId, runId }: { projectId: string; runId: string }) {
  const { t } = useI18n();
  const { runs, trackRun } = useProjectAgentEvents(projectId);
  const [agentRunId, setAgentRunId] = useState<string | null>(null);

  const mutation = useMutation<{ agent_run_id: string }, ApiError>({
    mutationFn: () => analyzeRun(projectId, runId),
    onSuccess: (res) => { setAgentRunId(res.agent_run_id); trackRun(res.agent_run_id); },
  });

  const live = agentRunId ? runs[agentRunId] : undefined;
  const busy = mutation.isPending || live?.status === 'running';

  return (
    <div>
      <button onClick={() => mutation.mutate()} disabled={busy}
        className="rounded-md bg-accent px-4 py-2 text-xs font-medium text-accent-fg hover:bg-accent-hover disabled:opacity-40">
        {busy ? t('experiments.analyzing') : live?.status === 'completed' ? '✓ Complete' : t('experiments.analyze')}
      </button>
      {live && (
        <div className="mt-3 rounded-lg border border-border bg-surface p-4">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-faint">{t('experiments.analysisResult')}</p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted">{live.text || '…'}</p>
          {live.status === 'failed' && <p className="mt-1 text-sm text-danger">{live.error}</p>}
        </div>
      )}
    </div>
  );
}
