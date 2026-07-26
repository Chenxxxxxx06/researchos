/**
 * Local WebSocket types for the IDE realtime client. Control frames are typed
 * here (no compile-time dependency on shared-schemas changing); they mirror the
 * ping/pong contract in CONSOLIDATION §4.
 */

export type ConnectionState = 'connecting' | 'open' | 'reconnecting' | 'offline' | 'closed';

export interface SocketStatus {
  state: ConnectionState;
  /** Reconnect attempt count (0 while open). */
  attempt: number;
  lastOpenAt: number | null;
}

/** Client → server heartbeat. */
export interface WsPing {
  type: 'ping';
  ts: number;
}

/** Server → client heartbeat echo (ts null when the ping carried none). */
export interface WsPong {
  type: 'pong';
  ts: number | null;
}

export type StatusKind = 'open' | 'reopen' | 'down';
