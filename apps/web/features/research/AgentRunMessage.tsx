import type { LiveRun } from '@/lib/websocket/useProjectAgentEvents';

import { CitationChip } from './CitationChip';
import { ToolCallChip } from './ToolCallChip';

/** Renders a streaming or completed assistant turn. */
export function AgentRunMessage({ run }: { run: LiveRun }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-3">
      <div className="mb-1 flex items-center gap-2">
        <span className="text-xs font-semibold text-neutral-500">Assistant</span>
        {run.status === 'running' && (
          <span className="text-xs text-amber-600">streaming…</span>
        )}
        {run.status === 'failed' && <span className="text-xs text-red-600">failed</span>}
      </div>

      {run.toolCalls.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {run.toolCalls.map((t) => (
            <ToolCallChip key={t.seq} tool={t} />
          ))}
        </div>
      )}

      <p className="whitespace-pre-wrap text-sm text-neutral-800">
        {run.text || (run.status === 'running' ? '…' : '')}
      </p>
      {run.error && <p className="mt-1 text-sm text-red-600">{run.error}</p>}

      {run.citations.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {run.citations.map((c) => (
            <CitationChip
              key={`${c.source}:${c.external_id}`}
              citation={{ label: `${c.source}:${c.external_id}`, url: c.url }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
