'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { createAgentRun } from '@/lib/api/agents';
import { ApiError } from '@/lib/api/client';
import { listLLMConfigs } from '@/lib/api/llmConfig';
import { useI18n } from '@/lib/i18n';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';

export function PaperAssistant({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const { runs, trackRun } = useProjectAgentEvents(projectId);
  const [message, setMessage] = useState('');
  const [runId, setRunId] = useState<string | null>(null);

  const llmConfigs = useQuery({ queryKey: ['llm-configs', projectId], queryFn: () => listLLMConfigs(projectId) });
  const hasRealLLM = (llmConfigs.data?.length ?? 0) > 0;

  const ask = useMutation<{ agent_run_id: string }, ApiError, string>({
    mutationFn: (msg) => createAgentRun(projectId, { agent_type: 'latex' as 'research', message: msg }),
    onSuccess: (res) => { trackRun(res.agent_run_id); setRunId(res.agent_run_id); setMessage(''); },
  });

  const run = runId ? runs[runId] : undefined;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-2.5">
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-neutral-400">{t('paper.assistant')}</h3>
        {!hasRealLLM && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] text-amber-700">Mock</span>}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {!run && !ask.isPending && <p className="text-xs text-neutral-400">{t('paper.askAssistant')}</p>}
        {run?.text && <pre className="whitespace-pre-wrap text-xs leading-relaxed text-neutral-800">{run.text}</pre>}
        {(run?.status === 'running' && !run.text) && <p className="text-xs text-neutral-400 animate-pulse">…</p>}
      </div>
      <form className="space-y-2 border-t border-neutral-200 p-3" onSubmit={(e) => { e.preventDefault(); if (message.trim()) ask.mutate(message.trim()); }}>
        <textarea className="h-20 w-full rounded-lg border border-neutral-300 bg-neutral-50 p-2 text-xs placeholder:text-neutral-400 resize-none" placeholder={t('paper.askAssistant')} value={message} onChange={(e) => setMessage(e.target.value)} />
        <button type="submit" disabled={ask.isPending || !message.trim()} className="rounded-lg bg-neutral-900 px-3 py-1.5 text-[11px] font-medium text-white hover:bg-neutral-800 disabled:opacity-40">{ask.isPending ? '…' : t('paper.send')}</button>
      </form>
    </div>
  );
}
