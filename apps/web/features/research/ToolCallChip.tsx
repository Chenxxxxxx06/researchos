import type { LiveToolCall } from '@/lib/websocket/useProjectAgentEvents';

export function ToolCallChip({ tool }: { tool: LiveToolCall }) {
  const colors: Record<string, string> = {
    started: 'border-amber-200 bg-amber-50 text-amber-700',
    succeeded: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    failed: 'border-red-200 bg-red-50 text-red-700',
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${colors[tool.status] ?? colors.started}`}>
      {tool.status === 'started' && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />}
      {tool.status === 'succeeded' && '✓ '}
      {tool.tool_name}
    </span>
  );
}
