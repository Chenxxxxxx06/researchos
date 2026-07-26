'use client';

import { Check, X } from 'lucide-react';

import type { LiveToolCall } from '@/lib/websocket/useProjectAgentEvents';
import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

const STYLES: Record<LiveToolCall['status'], string> = {
  started: 'bg-warn-bg text-warn',
  succeeded: 'bg-success-bg text-success',
  failed: 'bg-danger-bg text-danger',
};

const TITLE_KEY = {
  started: 'research.tool.running',
  succeeded: 'research.tool.done',
  failed: 'research.tool.failed',
} as const;

export function ToolCallChip({ tool }: { tool: LiveToolCall }) {
  const { t } = useI18n();
  const style = STYLES[tool.status] ?? STYLES.started;
  return (
    <span
      title={t(TITLE_KEY[tool.status] ?? TITLE_KEY.started, { tool: tool.tool_name })}
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium',
        style,
      )}
    >
      {tool.status === 'started' && (
        <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {tool.status === 'succeeded' && <Check className="h-3 w-3" aria-hidden="true" />}
      {tool.status === 'failed' && <X className="h-3 w-3" aria-hidden="true" />}
      <span className="font-mono">{tool.tool_name}</span>
    </span>
  );
}
