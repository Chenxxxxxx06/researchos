'use client';

import type { EventEnvelope } from '@researchos/shared-schemas';
import { useCallback, useEffect, useRef, useState } from 'react';

import { getAgentRunEvents } from '@/lib/api/agents';

import { projectSockets } from './client';
import type { SocketStatus } from './types';

// --- Public shapes (preserved for ResearchChat / PaperAssistant / AnalysisPanel /
//     AgentRunMessage / ToolCallChip — do not narrow) ---------------------------

export interface LiveToolCall {
  seq: number;
  tool_name: string;
  status: 'started' | 'succeeded' | 'failed';
  /** Additive: raw call arguments for the IDE tool chip's path/pattern preview. */
  args?: Record<string, unknown>;
}

export interface LiveRun {
  runId: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  text: string;
  citations: { source: string; external_id: string; title: string; url: string }[];
  toolCalls: LiveToolCall[];
  error?: string;
}

type Runs = Record<string, LiveRun>;

interface RunInternal {
  lastCoarseSeq: number; // max persisted-event seq folded so far
  lastTokenSeq: number; // -1 when the server sends no token seq
  terminal: boolean;
  updatedAt: number;
}

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);
const MAX_RUNS = 50;

function ensure(runs: Runs, runId: string): LiveRun {
  return runs[runId] ?? { runId, status: 'running', text: '', citations: [], toolCalls: [] };
}

function isTerminal(status: LiveRun['status']): boolean {
  return TERMINAL.has(status);
}

/** Idempotent fold: safe to re-apply (replay overlaps live). Returns whether the run changed. */
function foldEvent(
  run: LiveRun,
  internal: RunInternal,
  eventType: string,
  payload: Record<string, unknown>,
): boolean {
  switch (eventType) {
    case 'agent.run.started':
      if (isTerminal(run.status)) return false;
      run.status = 'running';
      return true;
    case 'agent.run.token': {
      const seq = typeof payload.seq === 'number' ? payload.seq : null;
      if (seq !== null) {
        if (seq <= internal.lastTokenSeq) return false; // stale / dup
        internal.lastTokenSeq = seq;
      }
      run.text += typeof payload.delta === 'string' ? payload.delta : '';
      return true;
    }
    case 'agent.run.tool_call.started': {
      const seq = Number(payload.seq);
      const toolName = typeof payload.tool_name === 'string' ? payload.tool_name : 'tool';
      const args =
        payload.arguments && typeof payload.arguments === 'object'
          ? (payload.arguments as Record<string, unknown>)
          : undefined;
      const idx = run.toolCalls.findIndex((t) => t.seq === seq);
      if (idx >= 0) {
        // Keep an already-final status (out-of-order completed before started).
        run.toolCalls = run.toolCalls.map((t, i) =>
          i === idx ? { ...t, tool_name: toolName, args: args ?? t.args } : t,
        );
      } else {
        run.toolCalls = [...run.toolCalls, { seq, tool_name: toolName, status: 'started', args }];
      }
      return true;
    }
    case 'agent.run.tool_call.completed': {
      const seq = Number(payload.seq);
      const status = payload.status === 'succeeded' ? 'succeeded' : 'failed';
      const toolName = typeof payload.tool_name === 'string' ? payload.tool_name : undefined;
      const idx = run.toolCalls.findIndex((t) => t.seq === seq);
      if (idx >= 0) {
        run.toolCalls = run.toolCalls.map((t, i) => (i === idx ? { ...t, status } : t));
      } else {
        run.toolCalls = [
          ...run.toolCalls,
          { seq, tool_name: toolName ?? 'tool', status },
        ];
      }
      return true;
    }
    case 'agent.run.completed': {
      if (isTerminal(run.status)) return false;
      run.status = 'completed';
      if (typeof payload.output === 'string') run.text = payload.output;
      run.citations = Array.isArray(payload.citations)
        ? (payload.citations as LiveRun['citations'])
        : [];
      return true;
    }
    case 'agent.run.failed': {
      if (isTerminal(run.status)) return false;
      run.status = 'failed';
      run.error = typeof payload.error === 'string' ? payload.error : 'Run failed';
      return true;
    }
    case 'agent.run.cancelled':
      if (isTerminal(run.status)) return false;
      run.status = 'cancelled';
      return true;
    default:
      return false;
  }
}

function evict(runs: Runs, internals: Record<string, RunInternal>): Runs {
  const terminalIds = Object.keys(runs).filter((id) => internals[id]?.terminal);
  if (terminalIds.length <= MAX_RUNS) return runs;
  terminalIds.sort((a, b) => (internals[b]?.updatedAt ?? 0) - (internals[a]?.updatedAt ?? 0));
  const drop = terminalIds.slice(MAX_RUNS);
  const next = { ...runs };
  for (const id of drop) {
    delete next[id];
    delete internals[id];
  }
  return next;
}

/**
 * Subscribe to a project's agent-run events over the shared socket and expose a
 * live, idempotent per-run accumulator. Public API is unchanged from the
 * original hook; `trackRun` now also replays persisted events (closing the
 * POST→subscribe race) and a socket reopen reconciles via REST replay.
 */
export function useProjectAgentEvents(projectId: string) {
  const [runs, setRuns] = useState<Runs>({});
  const internalsRef = useRef<Record<string, RunInternal>>({});
  const replayRef = useRef<(runId: string, afterSeq: number, retry: boolean) => void>(() => {});

  const apply = useCallback(
    (runId: string, eventType: string, payload: Record<string, unknown>, coarseSeq?: number) => {
      setRuns((prev) => {
        const internal =
          internalsRef.current[runId] ??
          ({ lastCoarseSeq: -1, lastTokenSeq: -1, terminal: false, updatedAt: 0 } as RunInternal);
        const run = { ...ensure(prev, runId) };
        const changed = foldEvent(run, internal, eventType, payload);
        if (coarseSeq !== undefined && coarseSeq > internal.lastCoarseSeq) {
          internal.lastCoarseSeq = coarseSeq;
        }
        internal.terminal = isTerminal(run.status);
        internal.updatedAt = Date.now();
        internalsRef.current[runId] = internal;
        if (!changed) return prev;
        return evict({ ...prev, [runId]: run }, internalsRef.current);
      });
    },
    [],
  );

  useEffect(() => {
    const acq = projectSockets.acquire(projectId);

    const replay = async (runId: string, afterSeq: number, allowRetry: boolean): Promise<void> => {
      try {
        const events = await getAgentRunEvents(projectId, runId, afterSeq);
        for (const e of events) apply(runId, e.event_type, e.payload_json, e.seq);
      } catch (err) {
        console.warn('[ws] event replay failed', err);
        if (allowRetry) setTimeout(() => void replay(runId, afterSeq, false), 1000);
      }
    };
    replayRef.current = (runId, afterSeq, retry) => void replay(runId, afterSeq, retry);

    const unsubEvents = acq.subscribe((env: EventEnvelope) => {
      if (env.resource_type !== 'agent_run') return;
      apply(env.resource_id, env.event_type, env.payload as Record<string, unknown>);
    });
    const unsubStatus = acq.subscribeStatus((_status, kind) => {
      if (kind !== 'reopen') return;
      for (const [runId, internal] of Object.entries(internalsRef.current)) {
        if (!internal.terminal) void replay(runId, internal.lastCoarseSeq, false);
      }
    });

    return () => {
      unsubEvents();
      unsubStatus();
      acq.release();
      replayRef.current = () => {};
    };
  }, [projectId, apply]);

  const trackRun = useCallback((runId: string) => {
    setRuns((prev) => (prev[runId] ? prev : { ...prev, [runId]: ensure(prev, runId) }));
    if (!internalsRef.current[runId]) {
      internalsRef.current[runId] = {
        lastCoarseSeq: -1,
        lastTokenSeq: -1,
        terminal: false,
        updatedAt: Date.now(),
      };
    }
    replayRef.current(runId, -1, true);
  }, []);

  return { runs, trackRun };
}

/** Live connection status for the reconnection pill (additive export). */
export function useProjectConnection(projectId: string): SocketStatus {
  const [status, setStatus] = useState<SocketStatus>({
    state: 'connecting',
    attempt: 0,
    lastOpenAt: null,
  });
  useEffect(() => {
    const acq = projectSockets.acquire(projectId);
    const unsub = acq.subscribeStatus((s) => setStatus({ ...s }));
    setStatus({ ...acq.getStatus() });
    return () => {
      unsub();
      acq.release();
    };
  }, [projectId]);
  return status;
}
