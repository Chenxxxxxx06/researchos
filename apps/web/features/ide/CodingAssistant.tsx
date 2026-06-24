'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { createCodingRun } from '@/lib/api/codingAgent';
import { listLLMConfigs } from '@/lib/api/llmConfig';

export function CodingAssistant({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState('');

  const llmConfigs = useQuery({ queryKey: ['llm-configs', projectId], queryFn: () => listLLMConfigs(projectId) });
  const hasRealLLM = (llmConfigs.data?.length ?? 0) > 0;

  const run = useMutation({
    mutationFn: () => createCodingRun(projectId, message),
    onSuccess: () => {
      setMessage('');
      for (let i = 1; i <= 5; i++) setTimeout(() => queryClient.invalidateQueries({ queryKey: ['patches', projectId] }), i * 1200);
    },
  });

  return (
    <div className="border-b border-neutral-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-neutral-400">Coding assistant</h3>
        {!hasRealLLM && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] text-amber-700">Mock LLM</span>}
      </div>
      <p className="text-xs text-neutral-500">Describe the change. The agent inspects the workspace and proposes a patch for your review.</p>
      <form className="mt-2 space-y-2" onSubmit={(e) => { e.preventDefault(); if (message.trim()) run.mutate(); }}>
        <textarea className="h-16 w-full rounded-lg border border-neutral-300 bg-neutral-50 p-2 text-xs placeholder:text-neutral-400 resize-none" placeholder="e.g. Add a utils helper function…" value={message} onChange={(e) => setMessage(e.target.value)} />
        <button type="submit" disabled={run.isPending || !message.trim()} className="rounded-lg bg-neutral-900 px-3 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-neutral-800 disabled:opacity-40">
          {run.isPending ? 'Generating…' : 'Generate patch'}
        </button>
      </form>
    </div>
  );
}
