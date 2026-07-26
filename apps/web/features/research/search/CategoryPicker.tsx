'use client';

import { Check, ChevronDown, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

import { categoryLabel, groupCategories } from './arxivTaxonomy';

/**
 * Keyboard-accessible checkbox popover over the curated arXiv taxonomy, plus a
 * removable-chip row of the current selection. Pure native elements (no popper /
 * combobox dep); reused by the search query builder and the feed editor.
 */
export function CategoryPicker({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const groups = groupCategories();
  const selectedSet = new Set(selected);

  const toggle = useCallback(
    (id: string) => {
      onChange(selectedSet.has(id) ? selected.filter((c) => c !== id) : [...selected, id]);
    },
    [onChange, selected, selectedSet],
  );

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'inline-flex w-full items-center justify-between gap-1 rounded-md border border-border-strong',
          'bg-surface px-2.5 py-1.5 text-xs text-text hover:bg-surface-2',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60',
        )}
      >
        <span>
          {t('research.search.categories')}
          {selected.length > 0 && (
            <span className="ml-1 rounded-full bg-accent px-1.5 text-[10px] font-semibold text-accent-fg">
              {selected.length}
            </span>
          )}
        </span>
        <ChevronDown className={cn('h-3.5 w-3.5 text-muted transition-transform', open && 'rotate-180')} aria-hidden="true" />
      </button>

      {open && (
        <div
          role="group"
          className="absolute left-0 top-full z-40 mt-1 max-h-72 w-72 overflow-y-auto rounded-md border border-border bg-overlay p-2 shadow-elev2"
        >
          {groups.map((g) => (
            <div key={g.group} className="mb-2 last:mb-0">
              <p className="px-1 py-1 text-[10px] font-semibold uppercase tracking-wide text-faint">{g.group}</p>
              {g.items.map((c) => {
                const on = selectedSet.has(c.id);
                return (
                  <label
                    key={c.id}
                    className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-xs text-text hover:bg-surface-2"
                  >
                    <span
                      className={cn(
                        'flex h-4 w-4 shrink-0 items-center justify-center rounded border',
                        on ? 'border-accent bg-accent text-accent-fg' : 'border-border-strong bg-surface',
                      )}
                    >
                      {on && <Check className="h-3 w-3" aria-hidden="true" />}
                    </span>
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={on}
                      onChange={() => toggle(c.id)}
                    />
                    <span className="font-mono text-[11px] text-muted">{c.id}</span>
                    <span className="truncate">{c.label}</span>
                  </label>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {selected.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {selected.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-muted"
            >
              <span className="font-mono">{id}</span>
              <span className="text-faint">{categoryLabel(id)}</span>
              <button
                type="button"
                onClick={() => toggle(id)}
                aria-label={`${categoryLabel(id)} ✕`}
                className="text-faint hover:text-danger"
              >
                <X className="h-3 w-3" aria-hidden="true" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
