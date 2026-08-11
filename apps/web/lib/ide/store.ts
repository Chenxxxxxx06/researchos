/**
 * IDE editor + layout store (D6, v2). Replaces the un-owned `lib/store/ide.ts`.
 * `EditorPane` and `FileTree` are its only consumers (both owned).
 *
 * Dirty model: a buffer exists in `buffers` iff it differs from the server
 * content it forked from. `baseSha` is the sha of that forked content — captured
 * at first keystroke and never overwritten by later refetches, so a proposed
 * patch always carries the base the user actually edited (fixes gap #55).
 */

import { create } from 'zustand';

export interface Buffer {
  content: string;
  /** Sha of the server content this buffer forked from (first keystroke). */
  baseSha: string | null;
}

export type RightTab = 'chat' | 'git';

export interface IdeState {
  tabs: string[];
  active: string | null;
  buffers: Record<string, Buffer>;
  pendingReveal: { path: string; line: number } | null;
  selectedCommitSha: string | null;
  highlightTurnRunId: string | null;
  rightTab: RightTab;

  openTab: (path: string) => void;
  setActive: (path: string | null) => void;
  openFileAtLine: (path: string, line: number) => void;
  requestCloseTab: (path: string) => 'closed' | 'needs-confirm';
  forceCloseTab: (path: string) => void;
  setBuffer: (path: string, content: string, serverContent: string, serverSha: string | null) => void;
  reconcileServer: (path: string, serverContent: string) => void;
  clearReveal: () => void;
  revealTurn: (runId: string) => void;
  clearHighlight: () => void;
  selectCommit: (sha: string | null) => void;
  setRightTab: (tab: RightTab) => void;
  resetWorkspace: () => void;
}

function neighbor(tabs: string[], path: string): string | null {
  const idx = tabs.indexOf(path);
  const remaining = tabs.filter((t) => t !== path);
  if (remaining.length === 0) return null;
  // Prefer the tab that was to the left, else the new first.
  return remaining[Math.max(0, idx - 1)] ?? remaining[0] ?? null;
}

export const useIdeStore = create<IdeState>((set, get) => ({
  tabs: [],
  active: null,
  buffers: {},
  pendingReveal: null,
  selectedCommitSha: null,
  highlightTurnRunId: null,
  rightTab: 'chat',

  openTab: (path) =>
    set((s) => ({
      tabs: s.tabs.includes(path) ? s.tabs : [...s.tabs, path],
      active: path,
    })),

  setActive: (path) => set({ active: path }),

  openFileAtLine: (path, line) =>
    set((s) => ({
      tabs: s.tabs.includes(path) ? s.tabs : [...s.tabs, path],
      active: path,
      pendingReveal: { path, line },
    })),

  requestCloseTab: (path) => {
    const dirty = get().buffers[path] !== undefined;
    if (dirty) return 'needs-confirm';
    get().forceCloseTab(path);
    return 'closed';
  },

  forceCloseTab: (path) =>
    set((s) => {
      const tabs = s.tabs.filter((t) => t !== path);
      const buffers = { ...s.buffers };
      delete buffers[path];
      return {
        tabs,
        buffers,
        active: s.active === path ? neighbor(s.tabs, path) : s.active,
      };
    }),

  setBuffer: (path, content, serverContent, serverSha) =>
    set((s) => {
      const buffers = { ...s.buffers };
      if (content === serverContent) {
        // Typed back to the original — no longer dirty (fixes EditorPane :47).
        delete buffers[path];
      } else {
        const existing = buffers[path];
        buffers[path] = { content, baseSha: existing ? existing.baseSha : serverSha };
      }
      return { buffers };
    }),

  reconcileServer: (path, serverContent) =>
    set((s) => {
      const existing = s.buffers[path];
      if (!existing) return s;
      // Our own edit landed on disk — drop the now-redundant buffer.
      if (existing.content === serverContent) {
        const buffers = { ...s.buffers };
        delete buffers[path];
        return { buffers };
      }
      // Buffer still differs from fresh server content: keep it (never clobber);
      // EditorPane surfaces a non-blocking "changed on disk" chip.
      return s;
    }),

  clearReveal: () => set({ pendingReveal: null }),

  revealTurn: (runId) => set({ rightTab: 'chat', highlightTurnRunId: runId }),
  clearHighlight: () => set({ highlightTurnRunId: null }),

  selectCommit: (sha) => set(sha ? { selectedCommitSha: sha, rightTab: 'git' } : { selectedCommitSha: null }),
  setRightTab: (tab) => set({ rightTab: tab }),
  resetWorkspace: () => set({ tabs: [], active: null, buffers: {}, pendingReveal: null }),
}));
