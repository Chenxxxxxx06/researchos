'use client';

import { Sparkles } from 'lucide-react';

import type { Suggestion } from './suggestions';

/** Library-aware suggestion chip row (D7.5). Pure presentation — the parent
 *  maps each suggestion's action to prefill / seed / focus behavior. */
export function SuggestionChips({
  suggestions,
  onSelect,
}: {
  suggestions: Suggestion[];
  onSelect: (suggestion: Suggestion) => void;
}) {
  if (suggestions.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {suggestions.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => onSelect(s)}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] text-muted transition-colors hover:border-border-strong hover:bg-surface-2 hover:text-text"
        >
          <Sparkles className="h-3 w-3 shrink-0 text-accent" aria-hidden="true" />
          <span className="truncate">{s.label}</span>
        </button>
      ))}
    </div>
  );
}
