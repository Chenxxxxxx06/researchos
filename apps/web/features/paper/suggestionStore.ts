/**
 * Tracked-changes store (partition: frontend-paper, Design B.4).
 *
 * Per CONSOLIDATION §8 the server is authoritative for suggestions; this zustand
 * store is a CACHE of the server's proposed suggestions plus optimistic local
 * resolution (`dismissed`) so the UI updates instantly while a refetch confirms.
 * `shiftAfter` / `invalidateOverlapping` keep in-editor decorations aligned after
 * a local (dirty-buffer) apply, until the next server hydrate.
 */

import { create } from 'zustand';

import type { DocRange, Suggestion } from '@/lib/api/documents';

function lineCount(text: string): number {
  if (text === '') return 0;
  return text.split('\n').length;
}

function endsBefore(a: DocRange, b: DocRange): boolean {
  return a.end.line < b.start.line || (a.end.line === b.start.line && a.end.col <= b.start.col);
}

function overlaps(a: DocRange, b: DocRange): boolean {
  return !endsBefore(a, b) && !endsBefore(b, a);
}

interface SuggestionState {
  /** Proposed suggestions for the open file (single-file v1). */
  items: Suggestion[];
  /** Ids resolved locally (accepted/rejected) — filtered until next hydrate. */
  dismissed: Record<string, true>;
  /** Replace the cache from a server fetch, dropping already-dismissed ids. */
  hydrate: (list: Suggestion[]) => void;
  /** Optimistically remove a suggestion from view. */
  dismiss: (id: string) => void;
  /** Shift suggestions that start after `range` by `lineDelta` lines. */
  shiftAfter: (range: DocRange, lineDelta: number) => void;
  /** Drop suggestions whose range overlaps the edited range. */
  invalidateOverlapping: (range: DocRange) => void;
  clear: () => void;
}

export const useSuggestionStore = create<SuggestionState>((set) => ({
  items: [],
  dismissed: {},
  hydrate: (list) =>
    set((s) => ({ items: list.filter((sug) => !s.dismissed[sug.id]) })),
  dismiss: (id) =>
    set((s) => ({
      items: s.items.filter((sug) => sug.id !== id),
      dismissed: { ...s.dismissed, [id]: true },
    })),
  shiftAfter: (range, lineDelta) =>
    set((s) => ({
      items:
        lineDelta === 0
          ? s.items
          : s.items.map((sug) => {
              if (!endsBefore(range, sug.range)) return sug;
              return {
                ...sug,
                range: {
                  start: { line: sug.range.start.line + lineDelta, col: sug.range.start.col },
                  end: { line: sug.range.end.line + lineDelta, col: sug.range.end.col },
                },
              };
            }),
    })),
  invalidateOverlapping: (range) =>
    set((s) => ({ items: s.items.filter((sug) => !overlaps(sug.range, range)) })),
  clear: () => set({ items: [], dismissed: {} }),
}));

export { lineCount };
