'use client';

/**
 * Tool-call chip for a coding turn: "⚙ workspace.read apps/api/…/service.py ✓".
 * Fed by live tool events (or persisted replay events) via the run accumulator.
 */

import { Check, Loader2, Wrench, X } from 'lucide-react';

import type { LiveToolCall } from '@/lib/websocket/useProjectAgentEvents';

const ARG_KEYS = ['path', 'file_path', 'pattern', 'query', 'glob', 'command'];

function argPreview(args?: Record<string, unknown>): string | null {
  if (!args) return null;
  for (const key of ARG_KEYS) {
    const value = args[key];
    if (typeof value === 'string' && value.length > 0) return value;
  }
  return null;
}

export function IdeToolCallChip({ call }: { call: LiveToolCall }) {
  const arg = argPreview(call.args);
  return (
    <div className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-border bg-surface-2 px-2 py-1 text-xs">
      <Wrench className="h-3 w-3 shrink-0 text-muted" aria-hidden="true" />
      <span className="font-mono text-text">{call.tool_name}</span>
      {arg && <span className="truncate font-mono text-muted" title={arg}>{arg}</span>}
      {call.status === 'started' && (
        <Loader2 className="h-3 w-3 shrink-0 animate-spin text-muted" aria-hidden="true" />
      )}
      {call.status === 'succeeded' && <Check className="h-3 w-3 shrink-0 text-success" aria-hidden="true" />}
      {call.status === 'failed' && <X className="h-3 w-3 shrink-0 text-danger" aria-hidden="true" />}
    </div>
  );
}
