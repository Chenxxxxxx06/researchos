'use client';

import { SlidersHorizontal } from 'lucide-react';
import { useState } from 'react';

import type { SearchFilters } from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

import { CategoryPicker } from './CategoryPicker';

/** UI-side filter state (strings for the native date/text inputs). */
export interface SearchFormFilters {
  categories: string[];
  dateFrom: string;
  dateTo: string;
  author: string;
  title: string;
  sort: 'relevance' | 'latest';
}

export const EMPTY_FILTERS: SearchFormFilters = {
  categories: [],
  dateFrom: '',
  dateTo: '',
  author: '',
  title: '',
  sort: 'relevance',
};

/** Count of non-default filter facets, for the collapsed badge. */
export function activeFilterCount(f: SearchFormFilters): number {
  return (
    f.categories.length +
    (f.dateFrom ? 1 : 0) +
    (f.dateTo ? 1 : 0) +
    (f.author.trim() ? 1 : 0) +
    (f.title.trim() ? 1 : 0) +
    (f.sort !== 'relevance' ? 1 : 0)
  );
}

/** True when any facet (including categories) is set — used to allow empty-query submit. */
export function hasAnyFilter(f: SearchFormFilters): boolean {
  return activeFilterCount(f) > 0;
}

/** Compile UI filters into the backend `SearchFilters` (offset injected by caller). */
export function toApiFilters(f: SearchFormFilters): SearchFilters {
  return {
    categories: f.categories.length ? f.categories : undefined,
    date_from: f.dateFrom || null,
    date_to: f.dateTo || null,
    author: f.author.trim() || null,
    title: f.title.trim() || null,
    sort: f.sort,
  };
}

export function QueryBuilder({
  filters,
  onChange,
}: {
  filters: SearchFormFilters;
  onChange: (next: SearchFormFilters) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const count = activeFilterCount(filters);
  const set = <K extends keyof SearchFormFilters>(key: K, value: SearchFormFilters[K]) =>
    onChange({ ...filters, [key]: value });

  return (
    <div className="rounded-md border border-border bg-surface">
      <div className="flex items-center justify-between px-2.5 py-1.5">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted hover:text-text"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
          {t('research.search.filters')}
          {count > 0 && (
            <span className="rounded-full bg-accent px-1.5 text-[10px] font-semibold text-accent-fg">{count}</span>
          )}
        </button>
        {count > 0 && (
          <button
            type="button"
            onClick={() => onChange(EMPTY_FILTERS)}
            className="text-[11px] text-faint hover:text-danger"
          >
            {t('research.search.reset')}
          </button>
        )}
      </div>

      {open && (
        <div className="space-y-2.5 border-t border-border p-2.5">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-muted">{t('research.search.categories')}</label>
            <CategoryPicker selected={filters.categories} onChange={(v) => set('categories', v)} />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="mb-1 block text-[11px] font-medium text-muted">{t('research.search.dateFrom')}</label>
              <Input
                type="date"
                value={filters.dateFrom}
                onChange={(e) => set('dateFrom', e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium text-muted">{t('research.search.dateTo')}</label>
              <Input
                type="date"
                value={filters.dateTo}
                onChange={(e) => set('dateTo', e.target.value)}
                className="h-8 text-xs"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-[11px] font-medium text-muted">{t('research.search.author')}</label>
            <Input
              value={filters.author}
              onChange={(e) => set('author', e.target.value)}
              className="h-8 text-xs"
            />
          </div>

          <div>
            <label className="mb-1 block text-[11px] font-medium text-muted">{t('research.search.fieldTitle')}</label>
            <Input
              value={filters.title}
              onChange={(e) => set('title', e.target.value)}
              className="h-8 text-xs"
            />
          </div>

          <div>
            <label className="mb-1 block text-[11px] font-medium text-muted">{t('research.search.sort')}</label>
            <div className="inline-flex rounded-md border border-border-strong p-0.5">
              {(['relevance', 'latest'] as const).map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => set('sort', opt)}
                  className={cn(
                    'rounded px-2.5 py-1 text-[11px] font-medium transition-colors',
                    filters.sort === opt ? 'bg-accent text-accent-fg' : 'text-muted hover:text-text',
                  )}
                >
                  {opt === 'relevance' ? t('research.search.sortRelevance') : t('research.search.sortLatest')}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
