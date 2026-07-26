import type { Idea } from '@/lib/api/ideas';
import { citationKey, type Paper } from '@/lib/api/papers';
import type { DictKey } from '@/lib/i18n';

import type { ChatSeed } from '../chatSeed';

type TFunc = (key: DictKey, params?: Record<string, string | number>) => string;

export type SuggestionAction =
  | { type: 'focus-discover' }
  | { type: 'message'; message: string }
  | { type: 'seed'; seed: ChatSeed; message: string };

export interface Suggestion {
  id: string;
  label: string;
  action: SuggestionAction;
}

function truncate(text: string, max = 40): string {
  const clean = text.trim();
  return clean.length > max ? `${clean.slice(0, max - 1)}…` : clean;
}

/**
 * Deterministic (no-LLM, mock-safe) suggestion chips (D7.5).
 *   - empty library → point the user at Discover.
 *   - non-empty     → summarize newest, connect recents, stress-test an idea.
 * Returns at most three entries.
 */
export function buildSuggestions(papers: Paper[], ideas: Idea[], t: TFunc): Suggestion[] {
  if (papers.length === 0) {
    return [{ id: 'search', label: t('research.chat.suggestSearch'), action: { type: 'focus-discover' } }];
  }

  const out: Suggestion[] = [];
  const newest = papers[0];
  out.push({
    id: 'summarize',
    label: t('research.chat.suggestSummarize', { title: truncate(newest.title) }),
    action: {
      type: 'seed',
      seed: {
        kind: 'paper',
        paperId: newest.id,
        paperTitle: newest.title,
        citationKey: citationKey(newest.source, newest.external_id),
      },
      message: t('research.chat.templatePaper'),
    },
  });

  if (papers.length > 1) {
    out.push({
      id: 'connect',
      label: t('research.chat.suggestConnect'),
      action: { type: 'message', message: t('research.chat.suggestConnect') },
    });
  }

  if (ideas.length > 0) {
    const idea = ideas[0];
    out.push({
      id: 'idea',
      label: t('research.chat.suggestIdea', { title: truncate(idea.title) }),
      action: {
        type: 'seed',
        seed: { kind: 'idea', ideaId: idea.id, ideaTitle: idea.title },
        message: t('research.chat.templateIdea'),
      },
    });
  }

  return out.slice(0, 3);
}
