'use client';

/**
 * Docked writing assistant (partition: frontend-paper, Design B.9). Replaces the
 * old PaperAssistant. Whole-document requests to the latex agent; live streaming
 * via the shared agent-events hook; history of prior latex runs; fenced ```latex
 * blocks in a response get an "Insert at cursor" button. Selection-scoped edits
 * go through the floating toolbar / tracked changes instead.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import { createLatexRun } from '@/lib/api/documents';
import { listAgentRuns, type AgentRun } from '@/lib/api/agents';
import { listLLMConfigs } from '@/lib/api/llmConfig';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { toast } from '@/components/ui/toast';
import { useI18n } from '@/lib/i18n';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';

interface Segment {
  kind: 'text' | 'code';
  text: string;
}

/** Split assistant output into prose + fenced ```latex/```tex code blocks. */
function parseSegments(output: string): Segment[] {
  const segments: Segment[] = [];
  const re = /```(?:latex|tex)?\n([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(output)) !== null) {
    if (m.index > last) segments.push({ kind: 'text', text: output.slice(last, m.index) });
    segments.push({ kind: 'code', text: m[1].replace(/\n$/, '') });
    last = re.lastIndex;
  }
  if (last < output.length) segments.push({ kind: 'text', text: output.slice(last) });
  return segments;
}

function AssistantAnswer({ text, onInsert }: { text: string; onInsert: (t: string) => void }) {
  const { t } = useI18n();
  if (!text) return null;
  return (
    <div className="space-y-2">
      {parseSegments(text).map((seg, i) =>
        seg.kind === 'code' ? (
          <div key={i} className="rounded-md border border-border bg-surface-2">
            <pre className="overflow-x-auto p-2 font-mono text-[11px] text-text">{seg.text}</pre>
            <div className="flex justify-end border-t border-border p-1">
              <Button size="sm" variant="ghost" onClick={() => onInsert(seg.text)}>
                {t('paper.assistant.insert')}
              </Button>
            </div>
          </div>
        ) : (
          <p key={i} className="whitespace-pre-wrap text-xs leading-relaxed text-text">
            {seg.text}
          </p>
        ),
      )}
    </div>
  );
}

export function AssistantDock({
  projectId,
  onInsert,
}: {
  projectId: string;
  latexProjectId: string;
  onInsert: (text: string) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { runs, trackRun } = useProjectAgentEvents(projectId);
  const [message, setMessage] = useState('');
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const llmConfigs = useQuery({
    queryKey: ['llm-configs', projectId],
    queryFn: () => listLLMConfigs(projectId),
    retry: false,
  });
  const hasRealLLM = (llmConfigs.data?.length ?? 0) > 0;

  const history = useQuery({
    queryKey: ['agent-runs', projectId, 'latex'],
    queryFn: () => listAgentRuns(projectId, { limit: 20 }),
    retry: false,
    select: (page) => page.items.filter((r) => r.agent_type === 'latex'),
  });

  const ask = useMutation<{ agent_run_id: string }, ApiError, string>({
    mutationFn: (msg) => createLatexRun(projectId, msg),
    onSuccess: (res) => {
      trackRun(res.agent_run_id);
      setActiveRunId(res.agent_run_id);
      setMessage('');
      qc.invalidateQueries({ queryKey: ['agent-runs', projectId, 'latex'] });
    },
    onError: () => toast({ title: t('paper.assistant.failed'), variant: 'error' }),
  });

  const liveRun = activeRunId ? runs[activeRunId] : undefined;
  const historyRun: AgentRun | undefined = !liveRun
    ? history.data?.find((r) => r.status === 'completed')
    : undefined;
  const displayText = liveRun?.text ?? historyRun?.output_json?.message ?? '';
  const isRunning = liveRun?.status === 'running';

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-muted">
          {t('paper.assistant')}
        </h3>
        {!hasRealLLM && (
          <Badge variant="warn" size="sm">
            {t('paper.assistant.mock')}
          </Badge>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {!displayText && !ask.isPending && !isRunning && (
          <p className="text-xs text-muted">{t('paper.assistant.empty')}</p>
        )}
        {(ask.isPending || (isRunning && !displayText)) && (
          <p className="animate-pulse text-xs text-muted">{t('paper.ai.thinking')}</p>
        )}
        <AssistantAnswer text={displayText} onInsert={onInsert} />
      </div>

      <form
        className="space-y-2 border-t border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (message.trim()) ask.mutate(message.trim());
        }}
      >
        <Textarea
          className="h-20 resize-none text-xs"
          placeholder={t('paper.assistant.wholeDoc')}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <Button
          type="submit"
          size="sm"
          className="w-full"
          disabled={ask.isPending || !message.trim()}
          loading={ask.isPending}
        >
          {t('paper.send')}
        </Button>
      </form>
    </div>
  );
}
