import type { LiveRun } from '@/lib/websocket/useProjectAgentEvents';

import { CitationChip } from './CitationChip';
import { ToolCallChip } from './ToolCallChip';

export function AgentRunMessage({ run }: { run: LiveRun }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-neutral-900 px-4 py-2.5 text-sm leading-relaxed text-white">
          {/* The user message isn't tracked in LiveRun; we show the run status instead */}
          <span className="text-xs text-neutral-400">{run.status === 'running' ? 'Processing…' : 'Done'}</span>
        </div>
      </div>

      <div className="flex justify-start">
        <div className="max-w-[90%] space-y-2">
          {run.toolCalls.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {run.toolCalls.map((t) => (
                <ToolCallChip key={t.seq} tool={t} />
              ))}
            </div>
          )}
          <div className="rounded-2xl rounded-bl-md border border-neutral-200 bg-white px-4 py-3 text-sm leading-relaxed text-neutral-800 shadow-sm">
            {run.status === 'running' && !run.text && (
              <span className="inline-flex items-center gap-1 text-neutral-400">
                <span className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
                Searching papers…
              </span>
            )}
            {run.text ? (
              <p className="whitespace-pre-wrap">{run.text}</p>
            ) : run.status === 'running' ? (
              <span className="animate-pulse text-neutral-400">…</span>
            ) : null}
            {run.error && <p className="mt-1 text-red-600">{run.error}</p>}
            {run.citations.length > 0 && (
              <div className="mt-2 border-t border-neutral-100 pt-2">
                <p className="mb-1 text-[11px] font-medium text-neutral-400">SOURCES</p>
                <div className="flex flex-wrap gap-1">
                  {run.citations.map((c) => (
                    <CitationChip key={`${c.source}:${c.external_id}`} citation={{ label: `${c.source}:${c.external_id}`, url: c.url }} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
