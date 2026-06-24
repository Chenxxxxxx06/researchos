import type { LiveToolCall } from '@/lib/websocket/useProjectAgentEvents';

export function ToolCallChip({ tool }: { tool: LiveToolCall }) {
  const color =
    tool.status === 'succeeded'
      ? 'bg-green-100 text-green-700'
      : tool.status === 'failed'
        ? 'bg-red-100 text-red-700'
        : 'bg-amber-100 text-amber-700';
  return (
    <span className={`rounded px-2 py-0.5 font-mono text-xs ${color}`}>
      {tool.tool_name} · {tool.status}
    </span>
  );
}
