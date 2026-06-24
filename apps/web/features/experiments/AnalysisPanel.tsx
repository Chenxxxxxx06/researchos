'use client';

import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { analyzeRun } from '@/lib/api/experiments';
import { ApiError } from '@/lib/api/client';
import { useI18n } from '@/lib/i18n';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';

export function AnalysisPanel({ projectId, runId }: { projectId: string; runId: string }) {
  const { t } = useI18n();
  const { runs, trackRun } = useProjectAgentEvents(projectId);
  const [agentRunId, setAgentRunId] = useState<string | null>(null);

  const mutation = useMutation<{ agent_run_id: string }, ApiError>({
    mutationFn: () => analyzeRun(projectId, runId),
    onSuccess: (res) => {
      setAgentRunId(res.agent_run_id);
      trackRun(res.agent_run_id);
    },
  });

  const live = agentRunId ? runs[agentRunId] : undefined;
  const isAnalyzing = mutation.isPending || live?.status === 'running';

  return (
    <div className="space-y-2">
      <Button size="sm" onClick={() => mutation.mutate()} disabled={isAnalyzing}>
        {isAnalyzing ? t('experiments.analyzing') : t('experiments.analyze')}
      </Button>

      {mutation.isError && <p className="text-xs text-red-600">{t('common.error')}</p>}

      {live && (
        <div className="rounded-md border border-neutral-200 bg-white p-3">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {t('experiments.analysisResult')}
          </p>
          <p className="whitespace-pre-wrap text-sm text-neutral-800">
            {live.text || (isAnalyzing ? t('experiments.analyzing') : '')}
          </p>
          {live.status === 'failed' && (
            <p className="mt-1 text-xs text-red-600">{live.error ?? t('common.error')}</p>
          )}
        </div>
      )}
    </div>
  );
}
