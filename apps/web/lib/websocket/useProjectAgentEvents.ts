'use client';

import type { AgentEventPayloadMap, EventEnvelope } from '@researchos/shared-schemas';
import { useCallback, useEffect, useRef, useState } from 'react';

import { connectProjectEvents } from './client';

export interface LiveToolCall {
  seq: number;
  tool_name: string;
  status: 'started' | 'succeeded' | 'failed';
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

function ensure(runs: Runs, runId: string): LiveRun {
  return runs[runId] ?? { runId, status: 'running', text: '', citations: [], toolCalls: [] };
}

/**
 * Subscribe to a project's agent-run events over WebSocket and expose a live,
 * per-run accumulator (tokens, tool calls, citations, status).
 */
export function useProjectAgentEvents(projectId: string) {
  const [runs, setRuns] = useState<Runs>({});
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = connectProjectEvents(projectId, (env: EventEnvelope) => {
      if (env.resource_type !== 'agent_run') return;
      const runId = env.resource_id;
      setRuns((prev) => {
        const run = { ...ensure(prev, runId) };
        applyEvent(run, env);
        return { ...prev, [runId]: run };
      });
    });
    wsRef.current = ws;
    return () => ws.close();
  }, [projectId]);

  const trackRun = useCallback((runId: string) => {
    setRuns((prev) => (prev[runId] ? prev : { ...prev, [runId]: ensure(prev, runId) }));
  }, []);

  return { runs, trackRun };
}

function applyEvent(run: LiveRun, env: EventEnvelope): void {
  switch (env.event_type) {
    case 'agent.run.started':
      run.status = 'running';
      break;
    case 'agent.run.token': {
      const p = env.payload as unknown as AgentEventPayloadMap['agent.run.token'];
      run.text += p.delta;
      break;
    }
    case 'agent.run.tool_call.started': {
      const p = env.payload as unknown as AgentEventPayloadMap['agent.run.tool_call.started'];
      run.toolCalls = [...run.toolCalls, { seq: p.seq, tool_name: p.tool_name, status: 'started' }];
      break;
    }
    case 'agent.run.tool_call.completed': {
      const p = env.payload as unknown as AgentEventPayloadMap['agent.run.tool_call.completed'];
      run.toolCalls = run.toolCalls.map((t) =>
        t.seq === p.seq ? { ...t, status: p.status === 'succeeded' ? 'succeeded' : 'failed' } : t,
      );
      break;
    }
    case 'agent.run.completed': {
      const p = env.payload as unknown as AgentEventPayloadMap['agent.run.completed'];
      run.status = 'completed';
      if (p.output) run.text = p.output;
      run.citations = p.citations ?? [];
      break;
    }
    case 'agent.run.failed': {
      const p = env.payload as unknown as AgentEventPayloadMap['agent.run.failed'];
      run.status = 'failed';
      run.error = p.error;
      break;
    }
    case 'agent.run.cancelled':
      run.status = 'cancelled';
      break;
  }
}
