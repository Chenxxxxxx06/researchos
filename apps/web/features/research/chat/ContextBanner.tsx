'use client';

import { BookOpen, Lightbulb, Puzzle, X, type LucideIcon } from 'lucide-react';

import { useI18n, type DictKey } from '@/lib/i18n';

import type { ChatSeed } from '../chatSeed';

function describe(seed: ChatSeed): { icon: LucideIcon; key: DictKey; params: Record<string, string> } {
  switch (seed.kind) {
    case 'section':
      return {
        icon: BookOpen,
        key: 'research.chat.contextSection',
        params: { title: seed.paperTitle, heading: seed.sectionHeading },
      };
    case 'paper':
      return { icon: BookOpen, key: 'research.chat.contextPaper', params: { title: seed.paperTitle } };
    case 'idea':
      return { icon: Lightbulb, key: 'research.chat.contextIdea', params: { title: seed.ideaTitle } };
    case 'gap':
      return {
        icon: Puzzle,
        key: 'research.chat.contextGap',
        params: { method: seed.method, problem: seed.problem },
      };
  }
}

/** Seed context pill shown above the composer (D6): kind icon + label + clear. */
export function ContextBanner({ seed, onClear }: { seed: ChatSeed; onClear: () => void }) {
  const { t } = useI18n();
  const { icon: Icon, key, params } = describe(seed);
  return (
    <div className="flex items-center gap-2 rounded-md border border-accent/40 bg-accent/10 px-2.5 py-1.5 text-xs text-text">
      <Icon className="h-3.5 w-3.5 shrink-0 text-accent" aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate">{t(key, params)}</span>
      <button
        type="button"
        onClick={onClear}
        aria-label={t('research.chat.clearContext')}
        className="shrink-0 text-muted hover:text-danger"
      >
        <X className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}
