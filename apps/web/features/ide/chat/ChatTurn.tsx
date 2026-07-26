'use client';

/**
 * One coding-chat turn: user bubble + assistant bubble (live-streaming text or
 * persisted reply) + tool-call chips + an inline DiffCard when the turn produced
 * a patch. Live overlay wins for text/status/tools; the persisted turn supplies
 * the user message and (once saved) the patch id — merge is keyed by run id, so
 * it survives re-order (fixes gap #53 for this surface).
 */

import type { CodingTurn } from '@/lib/api/codingAgent';
import { useI18n } from '@/lib/i18n';
import type { LiveRun } from '@/lib/websocket/useProjectAgentEvents';

import { DiffCard } from './DiffCard';
import { IdeToolCallChip } from './IdeToolCallChip';

export interface ChatTurnProps {
  projectId: string;
  turn: CodingTurn;
  live?: LiveRun;
  highlighted?: boolean;
}

export function ChatTurn({ projectId, turn, live, highlighted = false }: ChatTurnProps) {
  const { t } = useI18n();

  const status = live?.status ?? turn.status;
  const text = live && live.text.length > 0 ? live.text : turn.assistantMessage;
  const error = live?.error ?? turn.error;
  const toolCalls = live ? [...live.toolCalls].sort((a, b) => a.seq - b.seq) : [];
  const pending = status === 'queued' || status === 'running';
  const failed = status === 'failed' || status === 'cancelled';

  return (
    <div
      id={turn.agentRunId ? `turn-${turn.agentRunId}` : undefined}
      className={
        'space-y-2 rounded-lg transition-shadow ' +
        (highlighted ? 'ring-2 ring-accent ring-offset-2 ring-offset-bg' : '')
      }
    >
      {turn.userMessage && (
        <div className="flex justify-end">
          <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-accent px-3 py-2 text-sm text-accent-fg">
            {turn.userMessage}
          </div>
        </div>
      )}

      <div className="flex justify-start">
        <div className="w-full max-w-[92%] space-y-2">
          {toolCalls.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {toolCalls.map((call) => (
                <IdeToolCallChip key={call.seq} call={call} />
              ))}
            </div>
          )}

          {failed ? (
            <div className="rounded-2xl rounded-bl-sm border border-danger/40 bg-danger-bg px-3 py-2 text-sm text-danger">
              {error ?? t('ide.runFailed')}
            </div>
          ) : text ? (
            <div className="whitespace-pre-wrap break-words rounded-2xl rounded-bl-sm border border-border bg-surface-2 px-3 py-2 text-sm text-text">
              {text}
            </div>
          ) : pending ? (
            <div className="inline-flex items-center gap-2 rounded-2xl rounded-bl-sm border border-border bg-surface-2 px-3 py-2 text-sm text-muted">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden="true" />
              {t('ide.thinking')}
            </div>
          ) : null}

          {turn.patchId && <DiffCard projectId={projectId} patchId={turn.patchId} />}
        </div>
      </div>
    </div>
  );
}
