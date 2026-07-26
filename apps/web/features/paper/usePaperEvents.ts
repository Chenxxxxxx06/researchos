'use client';

/**
 * Tolerant paper-realtime wrapper (partition: frontend-paper, Design D.2).
 *
 * Dispatches the REAL backend event names (shared-schemas: `latex.compile.*`,
 * `figure.render.*`, `anchor.values.updated`) to optional handlers. Producers for
 * figure/anchor events are DEFERRED (CONSOLIDATION §4) — every handler is
 * optional and the panels carry themselves on polling fallbacks, so the UI is
 * fully functional before any producer lands. Unknown events are ignored.
 */

import type { EventEnvelope } from '@researchos/shared-schemas';
import { useEffect, useRef } from 'react';

import { projectSockets } from '@/lib/websocket/client';

export interface PaperEventHandlers {
  /** latex.compile.completed | latex.compile.failed */
  onCompile?: (payload: Record<string, unknown>, eventType: string) => void;
  /** figure.render.completed | figure.render.failed (resource_id = figure id) */
  onFigure?: (figureId: string, payload: Record<string, unknown>, eventType: string) => void;
  /** anchor.values.updated */
  onAnchors?: (payload: Record<string, unknown>) => void;
}

export function usePaperEvents(projectId: string, handlers: PaperEventHandlers): void {
  const ref = useRef(handlers);
  ref.current = handlers;

  useEffect(() => {
    const acq = projectSockets.acquire(projectId);
    const unsubscribe = acq.subscribe((env: EventEnvelope) => {
      const type = env.event_type as string;
      const payload = (env.payload ?? {}) as Record<string, unknown>;
      if (type === 'latex.compile.completed' || type === 'latex.compile.failed') {
        ref.current.onCompile?.(payload, type);
      } else if (type.startsWith('figure.render.')) {
        ref.current.onFigure?.(env.resource_id, payload, type);
      } else if (type === 'anchor.values.updated') {
        ref.current.onAnchors?.(payload);
      }
    });
    return () => {
      unsubscribe();
      acq.release();
    };
  }, [projectId]);
}
