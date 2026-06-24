'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { createCodingRun } from '@/lib/api/codingAgent';
import { Button } from '@/components/ui/button';

export function CodingAssistant({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState('');
  const [note, setNote] = useState<string | null>(null);

  const run = useMutation({
    mutationFn: () => createCodingRun(projectId, message),
    onSuccess: () => {
      setNote('Coding agent is generating a patch proposal…');
      setMessage('');
      // The worker creates a pending patch asynchronously; poll the patch list.
      for (let i = 1; i <= 5; i++) {
        setTimeout(
          () => queryClient.invalidateQueries({ queryKey: ['patches', projectId] }),
          i * 1200,
        );
      }
    },
  });

  return (
    <div className="border-b border-neutral-200 p-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Coding assistant
      </h3>
      <p className="mt-1 text-[11px] text-neutral-400">
        The agent proposes a patch for review. It never writes files directly.
      </p>
      <form
        className="mt-2 space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (message.trim()) run.mutate();
        }}
      >
        <textarea
          className="h-16 w-full rounded-md border border-neutral-300 p-2 text-xs"
          placeholder="Describe the change you want…"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <Button size="sm" type="submit" disabled={run.isPending || !message.trim()}>
          {run.isPending ? 'Starting…' : 'Generate patch'}
        </Button>
      </form>
      {note && <p className="mt-2 text-xs text-neutral-500">{note}</p>}
    </div>
  );
}
