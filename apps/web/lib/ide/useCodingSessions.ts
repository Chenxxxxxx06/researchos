'use client';

/**
 * Coding-chat session resolution (D3.1). Tries the canonical
 * `/coding-chat/sessions` route (CONSOLIDATION §1); on 404/405 it drops into
 * **fallback mode** — one implicit session whose turns are derived from coding
 * `agent_runs`. Either way the caller renders `CodingTurn[]`.
 *
 * The backend's message model is role-based (`messages: [{role, content,
 * agent_run_id, patch_id, …}]`); a "turn" is a user message plus the assistant
 * message sharing its `agent_run_id`. `messagesToTurns` folds that pairing.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { listAgentRuns, type AgentRun } from '@/lib/api/agents';
import { ApiError } from '@/lib/api/client';
import {
  createCodingSession,
  getCodingSession,
  listCodingSessions,
  type ChatMessage,
  type CodingSession,
  type CodingTurn,
} from '@/lib/api/codingAgent';

export type SessionMode = 'loading' | 'sessions' | 'fallback' | 'error';

const FALLBACK_LIMIT = 50;

function is404or405(err: unknown): boolean {
  return err instanceof ApiError && (err.status === 404 || err.status === 405);
}

/** Fold role-based messages into user+assistant turns keyed by `agent_run_id`. */
export function messagesToTurns(messages: ChatMessage[]): CodingTurn[] {
  const sorted = [...messages].sort((a, b) => a.seq - b.seq);
  const turns: CodingTurn[] = [];
  const byRun = new Map<string, CodingTurn>();

  for (const m of sorted) {
    if (m.role === 'user') {
      const turn: CodingTurn = {
        agentRunId: m.agent_run_id,
        seq: m.seq,
        userMessage: m.content,
        assistantMessage: null,
        patchId: m.patch_id,
        status: 'running', // provisional; live overlay / assistant reply refines it
        error: null,
        createdAt: m.created_at,
      };
      turns.push(turn);
      if (m.agent_run_id) byRun.set(m.agent_run_id, turn);
    } else {
      const turn = m.agent_run_id ? byRun.get(m.agent_run_id) : undefined;
      if (turn) {
        turn.assistantMessage = m.content;
        if (m.patch_id) turn.patchId = m.patch_id;
        turn.status = 'completed';
      } else {
        turns.push({
          agentRunId: m.agent_run_id,
          seq: m.seq,
          userMessage: '',
          assistantMessage: m.content,
          patchId: m.patch_id,
          status: 'completed',
          error: null,
          createdAt: m.created_at,
        });
      }
    }
  }
  return turns;
}

/** Map a coding agent run into a turn (fallback mode). */
export function runToTurn(run: AgentRun): CodingTurn {
  const patchId = (run.output_json?.patch_id ?? null) as string | null;
  return {
    agentRunId: run.id,
    seq: 0,
    userMessage: run.input_json.message ?? '',
    assistantMessage: run.output_json?.message ?? null,
    patchId,
    status: run.status,
    error: run.error_json?.message ?? null,
    createdAt: run.created_at,
  };
}

export interface CodingSessionsModel {
  mode: SessionMode;
  supported: boolean;
  sessions: CodingSession[];
  sessionsError: ApiError | null;
  activeSessionId: string | null;
  selectSession: (id: string | null) => void;
  createSession: (title?: string) => Promise<CodingSession>;
  creating: boolean;
  turns: CodingTurn[];
  turnsLoading: boolean;
  turnsError: ApiError | null;
  invalidateTurns: () => void;
  refetchSessions: () => void;
}

export function useCodingSessions(projectId: string): CodingSessionsModel {
  const queryClient = useQueryClient();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const sessionsQuery = useQuery({
    queryKey: ['coding-sessions', projectId],
    queryFn: () => listCodingSessions(projectId, { limit: FALLBACK_LIMIT }),
    retry: (_count, err) => !is404or405(err),
  });

  const unsupported = sessionsQuery.isError && is404or405(sessionsQuery.error);
  let mode: SessionMode;
  if (unsupported) mode = 'fallback';
  else if (sessionsQuery.isError) mode = 'error';
  else if (sessionsQuery.isLoading) mode = 'loading';
  else mode = 'sessions';

  const sessions = sessionsQuery.data?.items ?? [];
  const effectiveSessionId = activeSessionId ?? sessions[0]?.id ?? null;

  const detailQuery = useQuery({
    queryKey: ['coding-session', projectId, effectiveSessionId],
    queryFn: () => getCodingSession(projectId, effectiveSessionId as string),
    enabled: mode === 'sessions' && effectiveSessionId != null,
  });

  const fallbackQuery = useQuery({
    queryKey: ['coding-runs-fallback', projectId],
    queryFn: () => listAgentRuns(projectId, { limit: FALLBACK_LIMIT }),
    enabled: mode === 'fallback',
  });

  const createMutation = useMutation({
    mutationFn: (title: string) => createCodingSession(projectId, title),
    onSuccess: (session) => {
      setActiveSessionId(session.id);
      void queryClient.invalidateQueries({ queryKey: ['coding-sessions', projectId] });
    },
  });

  let turns: CodingTurn[] = [];
  if (mode === 'fallback') {
    turns = (fallbackQuery.data?.items ?? [])
      .filter((r) => r.agent_type === 'coding')
      .map(runToTurn)
      .reverse(); // listAgentRuns is newest-first; turns render ascending
  } else if (mode === 'sessions') {
    turns = messagesToTurns(detailQuery.data?.messages ?? []);
  }

  const invalidateTurns = () => {
    if (mode === 'fallback') {
      void queryClient.invalidateQueries({ queryKey: ['coding-runs-fallback', projectId] });
    } else {
      void queryClient.invalidateQueries({ queryKey: ['coding-session', projectId] });
    }
  };

  return {
    mode,
    supported: mode === 'sessions',
    sessions,
    sessionsError: unsupported ? null : ((sessionsQuery.error as ApiError | null) ?? null),
    activeSessionId: effectiveSessionId,
    selectSession: setActiveSessionId,
    createSession: (title = '') => createMutation.mutateAsync(title),
    creating: createMutation.isPending,
    turns,
    turnsLoading: mode === 'fallback' ? fallbackQuery.isLoading : detailQuery.isLoading,
    turnsError:
      mode === 'fallback'
        ? ((fallbackQuery.error as ApiError | null) ?? null)
        : ((detailQuery.error as ApiError | null) ?? null),
    invalidateTurns,
    refetchSessions: () => void sessionsQuery.refetch(),
  };
}
