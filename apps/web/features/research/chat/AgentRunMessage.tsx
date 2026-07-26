'use client';

import type { LiveRun } from '@/lib/websocket/useProjectAgentEvents';
import { useI18n } from '@/lib/i18n';

import { CitationChip } from '../CitationChip';
import { citationKey } from '@/lib/api/papers';
import { resolveCitation, toPayload, type LibraryMap } from '../citations';
import { ToolCallChip } from '../ToolCallChip';

/**
 * A live (streaming) chat turn (D7.1). The user bubble now renders the actual
 * prompt (threaded from `pendingPrompts`), falling back to a muted "(streaming
 * run)" only for runs started in another tab. Citations resolve through the
 * three-state integrity ladder.
 */
export function AgentRunMessage({
  run,
  prompt,
  projectId,
  library,
}: {
  run: LiveRun;
  prompt?: string;
  projectId: string;
  library: LibraryMap;
}) {
  const { t } = useI18n();
  const payload = toPayload(run.citations);

  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-sm leading-relaxed text-accent-fg">
          {prompt ? (
            <span className="whitespace-pre-wrap">{prompt}</span>
          ) : (
            <span className="text-accent-fg/70">{t('research.chat.streamingRun')}</span>
          )}
        </div>
      </div>

      <div className="flex justify-start">
        <div className="max-w-[90%] space-y-2">
          {run.toolCalls.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {run.toolCalls.map((tc) => (
                <ToolCallChip key={tc.seq} tool={tc} />
              ))}
            </div>
          )}

          <div className="rounded-2xl rounded-bl-md border border-border bg-surface px-4 py-3 text-sm leading-relaxed text-text shadow-elev1">
            {run.status === 'running' && !run.text && (
              <span className="inline-flex items-center gap-1.5 text-muted">
                <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
                {t('research.ingest.running')}
              </span>
            )}
            {run.text && <p className="whitespace-pre-wrap">{run.text}</p>}
            {run.error && <p className="mt-1 text-danger">{run.error}</p>}

            {run.citations.length > 0 && (
              <div className="mt-2 border-t border-border pt-2">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-faint">
                  {t('research.chat.sources')}
                </p>
                <div className="flex flex-wrap gap-1">
                  {run.citations.map((c) => {
                    const key = citationKey(c.source, c.external_id);
                    return (
                      <CitationChip
                        key={key}
                        projectId={projectId}
                        model={resolveCitation(key, payload, library)}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
