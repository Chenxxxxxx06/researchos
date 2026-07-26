import type { EventEnvelope } from '@researchos/shared-schemas';

import { API_BASE_URL } from '@/lib/api/client';

import type { SocketStatus, StatusKind, WsPing } from './types';

export function projectWsUrl(projectId: string): string {
  const base = API_BASE_URL.replace(/^http/, 'ws');
  return `${base}/ws?project_id=${encodeURIComponent(projectId)}`;
}

export type Listener = (env: EventEnvelope) => void;
export type StatusListener = (status: SocketStatus, kind: StatusKind) => void;

export interface Acquisition {
  subscribe(listener: Listener): () => void;
  subscribeStatus(listener: StatusListener): () => void;
  getStatus(): SocketStatus;
  release(): void;
}

const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 1_000;
const STABLE_MS = 5_000;
const PING_INTERVAL_MS = 25_000;
const PONG_PROBE_MS = 10_000;
const DEDUPE_CAP = 512;

// Session-remembered heartbeat capability (probed once, reused across sockets).
let pongCapable = false;
let heartbeatDisabled = false;

const isBrowser = typeof window !== 'undefined';

/** One managed WebSocket per projectId, shared across all subscribers. */
class ManagedSocket {
  private ws: WebSocket | null = null;
  private refCount = 0;
  private readonly listeners = new Set<Listener>();
  private readonly statusListeners = new Set<StatusListener>();
  private status: SocketStatus = { state: 'connecting', attempt: 0, lastOpenAt: null };

  private readonly seenIds = new Set<string>();
  private readonly seenOrder: string[] = [];

  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private stableTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private probeTimer: ReturnType<typeof setTimeout> | null = null;
  private missedPongs = 0;
  private openedOnce = false;
  private intentionalClose = false;

  private readonly onOnline = () => {
    if (this.status.state === 'offline') this.connect();
  };
  private readonly onVisible = () => {
    if (document.visibilityState === 'visible' && this.isDown()) {
      this.clearReconnectTimer();
      this.connect();
    }
  };

  constructor(private readonly projectId: string) {
    if (isBrowser) {
      window.addEventListener('online', this.onOnline);
      document.addEventListener('visibilitychange', this.onVisible);
    }
  }

  private isDown(): boolean {
    return (
      this.status.state === 'reconnecting' ||
      this.status.state === 'offline' ||
      this.status.state === 'closed'
    );
  }

  acquire(): Acquisition {
    this.refCount++;
    if (this.ws === null && this.reconnectTimer === null) this.connect();
    return {
      subscribe: (listener) => {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
      },
      subscribeStatus: (listener) => {
        this.statusListeners.add(listener);
        return () => this.statusListeners.delete(listener);
      },
      getStatus: () => this.status,
      release: () => this.release(),
    };
  }

  private release(): void {
    this.refCount = Math.max(0, this.refCount - 1);
    if (this.refCount === 0) this.teardown();
  }

  private teardown(): void {
    this.intentionalClose = true;
    this.clearTimers();
    if (isBrowser) {
      window.removeEventListener('online', this.onOnline);
      document.removeEventListener('visibilitychange', this.onVisible);
    }
    try {
      this.ws?.close();
    } catch {
      // ignore
    }
    this.ws = null;
    sockets.delete(this.projectId);
  }

  private setStatus(next: Partial<SocketStatus>, kind: StatusKind): void {
    this.status = { ...this.status, ...next };
    const snapshot = this.status;
    for (const l of this.statusListeners) l(snapshot, kind);
  }

  private connect(): void {
    if (!isBrowser) return;
    this.clearReconnectTimer();
    this.setStatus({ state: this.openedOnce ? 'reconnecting' : 'connecting' }, 'down');

    let ws: WebSocket;
    try {
      ws = new WebSocket(projectWsUrl(this.projectId));
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      const firstOpen = !this.openedOnce;
      this.openedOnce = true;
      this.missedPongs = 0;
      this.setStatus({ state: 'open', lastOpenAt: Date.now() }, firstOpen ? 'open' : 'reopen');
      // Reset the backoff counter once the connection proves stable.
      this.stableTimer = setTimeout(() => this.setStatus({ attempt: 0 }, 'reopen'), STABLE_MS);
      this.startHeartbeat();
    };

    ws.onmessage = (event) => this.handleMessage(event.data);

    ws.onerror = () => {
      // A close event follows; reconnection is handled there.
    };

    ws.onclose = () => {
      this.clearHeartbeat();
      if (this.stableTimer) {
        clearTimeout(this.stableTimer);
        this.stableTimer = null;
      }
      this.ws = null;
      if (this.intentionalClose || this.refCount === 0) {
        this.setStatus({ state: 'closed' }, 'down');
        return;
      }
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (!isBrowser) return;
    if (navigator.onLine === false) {
      this.setStatus({ state: 'offline' }, 'down');
      return; // wait for the `online` event
    }
    const attempt = this.status.attempt + 1;
    const jitter = 0.5 + Math.random() * 0.5; // full jitter in [0.5, 1.0)
    const delay = jitter * Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * 2 ** attempt);
    this.setStatus({ state: 'reconnecting', attempt }, 'down');
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private handleMessage(raw: unknown): void {
    let obj: unknown;
    try {
      obj = JSON.parse(typeof raw === 'string' ? raw : String(raw));
    } catch {
      console.warn('[ws] malformed frame', raw);
      return;
    }
    if (obj === null || typeof obj !== 'object') return;

    // Any delivered frame is evidence the link is healthy.
    if (this.status.attempt !== 0) this.setStatus({ attempt: 0 }, 'reopen');

    const record = obj as Record<string, unknown>;
    if (typeof record.type === 'string') {
      if (record.type === 'pong') {
        pongCapable = true;
        this.missedPongs = 0;
        if (this.probeTimer) {
          clearTimeout(this.probeTimer);
          this.probeTimer = null;
        }
      }
      return; // control frame (pong or unknown) — never fanned out
    }

    if (typeof record.event_type !== 'string') return;
    const eventId = typeof record.event_id === 'string' ? record.event_id : null;
    if (eventId) {
      if (this.seenIds.has(eventId)) return; // duplicate (replay overlap)
      this.seenIds.add(eventId);
      this.seenOrder.push(eventId);
      if (this.seenOrder.length > DEDUPE_CAP) {
        const evicted = this.seenOrder.shift();
        if (evicted) this.seenIds.delete(evicted);
      }
    }
    const env = obj as EventEnvelope;
    for (const l of this.listeners) l(env);
  }

  private send(frame: WsPing): void {
    try {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(frame));
    } catch {
      // ignore
    }
  }

  private startHeartbeat(): void {
    if (heartbeatDisabled) return;
    // Probe once per open; remember capability for the session.
    this.send({ type: 'ping', ts: Date.now() });
    if (!pongCapable) {
      this.probeTimer = setTimeout(() => {
        if (!pongCapable) heartbeatDisabled = true; // push-only gateway: stay silent
      }, PONG_PROBE_MS);
    }
    this.pingTimer = setInterval(() => {
      if (!pongCapable) return; // only loop once the server answered
      if (this.missedPongs >= 2) {
        try {
          this.ws?.close();
        } catch {
          // ignore
        }
        return;
      }
      this.missedPongs++;
      this.send({ type: 'ping', ts: Date.now() });
    }, PING_INTERVAL_MS);
  }

  private clearHeartbeat(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
    if (this.probeTimer) {
      clearTimeout(this.probeTimer);
      this.probeTimer = null;
    }
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private clearTimers(): void {
    this.clearReconnectTimer();
    this.clearHeartbeat();
    if (this.stableTimer) {
      clearTimeout(this.stableTimer);
      this.stableTimer = null;
    }
  }

  /** Dev/e2e-only: force-close the underlying socket to simulate a blip. */
  dropUnderlying(): void {
    try {
      this.ws?.close();
    } catch {
      // ignore
    }
  }
}

const sockets = new Map<string, ManagedSocket>();

export interface ProjectSocketManager {
  acquire(projectId: string): Acquisition;
}

export const projectSockets: ProjectSocketManager = {
  acquire(projectId: string): Acquisition {
    let socket = sockets.get(projectId);
    if (!socket) {
      socket = new ManagedSocket(projectId);
      sockets.set(projectId, socket);
    }
    return socket.acquire();
  },
};

// Dev/e2e hook: never installed in production builds.
declare global {
  interface Window {
    __rosSockets?: { drop(projectId: string): void };
  }
}
if (isBrowser && process.env.NODE_ENV !== 'production') {
  window.__rosSockets = {
    drop(projectId: string) {
      sockets.get(projectId)?.dropUnderlying();
    },
  };
}

/**
 * Back-compat shim over the manager (no external callers remain, but keeps the
 * old surface honest). Returns a WebSocket-shaped facade whose `close()`
 * releases the shared socket.
 */
export function connectProjectEvents(
  projectId: string,
  onEvent: Listener,
): Pick<WebSocket, 'close'> {
  const acq = projectSockets.acquire(projectId);
  const unsubscribe = acq.subscribe(onEvent);
  return {
    close: () => {
      unsubscribe();
      acq.release();
    },
  };
}
