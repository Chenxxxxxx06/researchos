import type { EventEnvelope } from '@researchos/shared-schemas';

import { API_BASE_URL } from '@/lib/api/client';

export function projectWsUrl(projectId: string): string {
  const base = API_BASE_URL.replace(/^http/, 'ws');
  return `${base}/ws?project_id=${encodeURIComponent(projectId)}`;
}

/**
 * Open a project-scoped event stream. The browser sends the session cookie with
 * the WebSocket handshake, which the backend validates against project
 * membership.
 */
export function connectProjectEvents(
  projectId: string,
  onEvent: (envelope: EventEnvelope) => void,
): WebSocket {
  const ws = new WebSocket(projectWsUrl(projectId));
  ws.onmessage = (event) => {
    try {
      onEvent(JSON.parse(event.data) as EventEnvelope);
    } catch {
      // Ignore malformed frames.
    }
  };
  return ws;
}
