'use client';

/**
 * Coding chat (D3): session-scoped history, live token streaming, tool chips,
 * and inline diff cards. Zero polling / zero blind invalidation — the shared
 * socket streams runs and a single completed/failed fold triggers exactly one
 * refetch of the turns + patches (CONSOLIDATION §4: patch/git WS events do not
 * exist, so refetch on run completion). Runs in sessions mode when the backend
 * has the `/coding-chat/sessions` route, else an implicit-session fallback.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';
import { createCodingRun, sendCodingMessage, type CodingTurn } from '@/lib/api/codingAgent';
import { ApiError } from '@/lib/api/client';
import { listLLMConfigs } from '@/lib/api/llmConfig';
import { listPatches } from '@/lib/api/patches';
import { useCodingSessions } from '@/lib/ide/useCodingSessions';
import { useIdeStore } from '@/lib/ide/store';
import { useI18n } from '@/lib/i18n';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';

import { ChatTurn } from './ChatTurn';
import { Composer } from './Composer';
import { DiffCard } from './DiffCard';
import { SessionBar } from './SessionBar';

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

export function CodingChat({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const sessions = useCodingSessions(projectId);
  const { runs, trackRun } = useProjectAgentEvents(projectId);

  const highlightRunId = useIdeStore((s) => s.highlightTurnRunId);
  const clearHighlight = useIdeStore((s) => s.clearHighlight);

  const [pending, setPending] = useState<CodingTurn[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const seenTerminal = useRef<Set<string>>(new Set());
  const trackedIncomplete = useRef<Set<string>>(new Set());

  const llmConfigs = useQuery({
    queryKey: ['llm-configs', projectId],
    queryFn: () => listLLMConfigs(projectId),
  });
  const hasRealLLM = Boolean(llmConfigs.data?.some((config) => config.is_active));

  const patchesQuery = useQuery({
    queryKey: ['patches', projectId],
    queryFn: () => listPatches(projectId, { limit: 50 }),
  });
  const manualPatches = (patchesQuery.data?.items ?? []).filter((p) => p.agent_run_id === null);

  const turnRunIds = useMemo(() => {
    const set = new Set<string>();
    for (const turn of sessions.turns) if (turn.agentRunId) set.add(turn.agentRunId);
    return set;
  }, [sessions.turns]);

  const livePending = pending.filter((p) => p.agentRunId != null && !turnRunIds.has(p.agentRunId));
  const allTurns = [...sessions.turns, ...livePending];

  // Drop optimistic turns once the real (persisted) turn arrives.
  useEffect(() => {
    setPending((prev) => {
      const next = prev.filter((p) => p.agentRunId != null && !turnRunIds.has(p.agentRunId));
      return next.length === prev.length ? prev : next;
    });
  }, [turnRunIds]);

  // Exactly one refetch per run that reaches a terminal state.
  useEffect(() => {
    let changed = false;
    for (const run of Object.values(runs)) {
      if (TERMINAL.has(run.status) && !seenTerminal.current.has(run.runId)) {
        seenTerminal.current.add(run.runId);
        changed = true;
      }
    }
    if (!changed) return;
    void queryClient.invalidateQueries({ queryKey: ['coding-session', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['coding-runs-fallback', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['patches', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['git-log', projectId] });
    void queryClient.invalidateQueries({ queryKey: ['git-status', projectId] });
  }, [runs, projectId, queryClient]);

  // Resume streaming/status for the newest still-open turn after a reload.
  useEffect(() => {
    const last = sessions.turns[sessions.turns.length - 1];
    if (last?.agentRunId && !last.assistantMessage && !trackedIncomplete.current.has(last.agentRunId)) {
      trackedIncomplete.current.add(last.agentRunId);
      trackRun(last.agentRunId);
    }
  }, [sessions.turns, trackRun]);

  // Scroll to a turn requested from the git timeline; flash-highlight for 2s.
  useEffect(() => {
    if (!highlightRunId) return;
    document.getElementById(`turn-${highlightRunId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const timer = setTimeout(() => clearHighlight(), 2000);
    return () => clearTimeout(timer);
  }, [highlightRunId, clearHighlight]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [allTurns.length, runs]);

  const appendPending = (text: string, runId: string) => {
    setPending((prev) => [
      ...prev,
      {
        agentRunId: runId,
        seq: Number.MAX_SAFE_INTEGER,
        userMessage: text,
        assistantMessage: null,
        patchId: null,
        status: 'queued',
        error: null,
        createdAt: new Date().toISOString(),
      },
    ]);
  };

  const send = async (text: string) => {
    try {
      let runId: string;
      if (sessions.supported) {
        let sessionId = sessions.activeSessionId;
        if (!sessionId) sessionId = (await sessions.createSession()).id;
        runId = (await sendCodingMessage(projectId, sessionId, text)).agent_run_id;
      } else {
        runId = (await createCodingRun(projectId, text)).agent_run_id;
      }
      appendPending(text, runId);
      trackRun(runId);
    } catch (err) {
      if (err instanceof ApiError && err.code === 'session_busy') {
        toast({ title: t('ide.sessionBusy'), variant: 'warning' });
        return;
      }
      toast({
        title: t('ide.runFailed'),
        description: err instanceof Error ? err.message : undefined,
        variant: 'error',
      });
    }
  };

  const busy =
    livePending.length > 0 ||
    sessions.turns.some((tn) => tn.agentRunId != null && runs[tn.agentRunId]?.status === 'running');

  const loading = allTurns.length === 0 && (sessions.mode === 'loading' || sessions.turnsLoading);
  const showError = sessions.mode === 'error' || (sessions.turnsError != null && allTurns.length === 0);
  const showEmpty = !loading && !showError && allTurns.length === 0 && manualPatches.length === 0;

  return (
    <div className="flex h-full flex-col bg-bg">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b border-border bg-surface px-3 py-2">
        <h2 className="text-sm font-semibold text-text">{t('ide.codingChat')}</h2>
        {!hasRealLLM && (
          <Badge variant="warn" size="sm">
            需要真实模型
          </Badge>
        )}
      </div>

      {sessions.supported && (
        <SessionBar
          sessions={sessions.sessions}
          activeSessionId={sessions.activeSessionId}
          onSelect={sessions.selectSession}
          onNew={() => void sessions.createSession()}
          creating={sessions.creating}
        />
      )}
      {!hasRealLLM && !llmConfigs.isLoading && (
        <div className="border-b border-warn/25 bg-warn-bg px-3 py-2 text-[10px] leading-4 text-warn">
          Coding Agent 已锁定，避免 Mock 补丁被当成真实修改。请在
          <Link href={`/projects/${projectId}/manage?tab=settings`} className="mx-1 font-semibold underline">管理中心</Link>
          配置并测试模型。
        </div>
      )}

      {/* Turns */}
      <div className="flex-1 space-y-4 overflow-y-auto px-3 py-4">
        {loading && (
          <div className="space-y-3">
            <Skeleton className="ml-auto h-10 w-2/3" />
            <Skeleton className="h-20 w-5/6" />
          </div>
        )}

        {showError && (
          <div className="rounded-lg border border-danger/40 bg-danger-bg p-3 text-sm text-danger">
            <p>{t('ide.chatFailed')}</p>
            <Button variant="outline" size="sm" className="mt-2" onClick={() => sessions.refetchSessions()}>
              {t('common.retry')}
            </Button>
          </div>
        )}

        {showEmpty && (
          <EmptyState icon={Bot} title={t('ide.chatEmptyTitle')} body={t('ide.chatEmptyBody')} />
        )}

        {allTurns.map((turn) => (
          <ChatTurn
            key={turn.agentRunId ?? `seq-${turn.seq}`}
            projectId={projectId}
            turn={turn}
            live={turn.agentRunId ? runs[turn.agentRunId] : undefined}
            highlighted={highlightRunId != null && highlightRunId === turn.agentRunId}
          />
        ))}

        {manualPatches.length > 0 && (
          <div className="space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
              {t('ide.manualChanges')}
            </p>
            {manualPatches.map((p) => (
              <DiffCard key={p.id} projectId={projectId} patchId={p.id} />
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <Composer onSend={send} disabled={!hasRealLLM || busy} busy={busy} />
    </div>
  );
}
