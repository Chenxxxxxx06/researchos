import { create } from 'zustand';

/**
 * A "carry this to the research chat" payload. Set by the Reading Room / Ideas
 * panel, consumed by `ResearchChat` to render a context banner, pre-fill a
 * template, and attach `context` to the agent run. Session-only (no persistence)
 * so navigating away and back keeps it until used.
 */
export type ChatSeed =
  | {
      kind: 'section';
      paperId: string;
      paperTitle: string;
      citationKey: string;
      sectionSeq: number;
      sectionHeading: string;
    }
  | { kind: 'paper'; paperId: string; paperTitle: string; citationKey: string }
  | { kind: 'innovation'; paperId: string; paperTitle: string; citationKey: string }
  | { kind: 'idea'; ideaId: string; ideaTitle: string }
  | { kind: 'gap'; problem: string; method: string; paperKeys: string[] };

interface ChatSeedState {
  seed: ChatSeed | null;
  setSeed: (seed: ChatSeed) => void;
  clear: () => void;
}

export const useChatSeedStore = create<ChatSeedState>((set) => ({
  seed: null,
  setSeed: (seed) => set({ seed }),
  clear: () => set({ seed: null }),
}));
