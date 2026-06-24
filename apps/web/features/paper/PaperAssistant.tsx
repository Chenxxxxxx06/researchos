'use client';

import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import { useI18n } from '@/lib/i18n';
import { ApiError } from '@/lib/api/client';
import { createAgentRun } from '@/lib/api/agents';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';
import { Button } from '@/components/ui/button';

export function PaperAssistant({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const { runs, trackRun } = useProjectAgentEvents(projectId);
  const [message, setMessage] = useState('');
  const [runId, setRunId] = useState<string | null>(null);

  const ask = useMutation<{ agent_run_id: string }, ApiError, string>({
    mutationFn: (msg: string) =>
      createAgentRun(projectId, { agent_type: 'latex' as 'research', message: msg }),
    onSuccess: (res) => {
      trackRun(res.agent_run_id);
      setRunId(res.agent_run_id);
      setMessage('');
    },
  });

  const run = runId ? runs[runId] : undefined;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-neutral-200 p-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          {t('paper.assistant')}
        </h3>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {!run && !ask.isPending && (
          <p className="text-xs text-neutral-400">{t('paper.askAssistant')}</p>
        )}
        {ask.isPending && !run?.text && (
          <p className="text-xs text-neutral-400">{t('common.loading')}</p>
        )}
        {run?.text && (
          <pre className="whitespace-pre-wrap text-xs leading-relaxed text-neutral-800">
            {run.text}
          </pre>
        )}
        {run?.status === 'failed' && (
          <p className="mt-2 text-xs text-red-600">{run.error ?? t('common.error')}</p>
        )}
        {ask.isError && (
          <p className="mt-2 text-xs text-red-600">{ask.error.message || t('common.error')}</p>
        )}
      </div>

      <form
        className="space-y-2 border-t border-neutral-200 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          const msg = message.trim();
          if (msg) ask.mutate(msg);
        }}
      >
        <textarea
          className="h-20 w-full rounded-md border border-neutral-300 p-2 text-xs"
          placeholder={t('paper.askAssistant')}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <Button size="sm" type="submit" disabled={ask.isPending || !message.trim()}>
          {ask.isPending ? t('common.loading') : t('paper.send')}
        </Button>
      </form>
    </div>
  );
}
