'use client';

import { NotebookPen, Sparkles } from 'lucide-react';
import { useState } from 'react';

import type { PaperSection } from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

const CLAMP_CHARS = 4000;
const CLAMP_TO = 1600;

/**
 * One section of the reading stream (D5.4): heading with a hover-revealed
 * "Explain this" button, and a plain-text body split into paragraphs on blank
 * lines. Very long bodies collapse to a "Show more" expander to keep the DOM
 * light. No markdown/LaTeX rendering — the body is plain text from the extractor.
 */
export function SectionCard({
  section,
  onExplain,
  onNote,
}: {
  section: PaperSection;
  onExplain: () => void;
  onNote?: () => void;
}) {
  const { t, locale } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const long = section.char_count > CLAMP_CHARS;
  const shown = long && !expanded ? `${section.body.slice(0, CLAMP_TO)}…` : section.body;
  const paragraphs = shown.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  const Heading = section.level <= 1 ? 'h2' : 'h3';

  return (
    <section id={`sec-${section.seq}`} className="group scroll-mt-4 border-b border-border pb-5 last:border-none">
      <div className="mb-2 flex items-center justify-between gap-2">
        <Heading
          className={cn(
            'font-semibold text-text',
            section.level <= 1 ? 'text-base' : 'text-sm',
          )}
        >
          {section.heading}
        </Heading>
        <div className="flex shrink-0 items-center opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
          {onNote && (
            <button type="button" onClick={onNote} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-muted hover:bg-surface-2 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60">
              <NotebookPen className="h-3 w-3" aria-hidden="true" />
              {locale === 'zh-CN' ? '笔记' : 'Note'}
            </button>
          )}
          <button
            type="button"
            onClick={onExplain}
            className={cn(
              'inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-accent',
              'hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60',
            )}
          >
            <Sparkles className="h-3 w-3" aria-hidden="true" />
            {t('research.reading.explainSection')}
          </button>
        </div>
      </div>

      <div className="space-y-2 text-sm leading-relaxed text-muted">
        {paragraphs.map((p, i) => (
          <p key={i} className="whitespace-pre-wrap">
            {p}
          </p>
        ))}
      </div>

      {long && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 text-[11px] font-medium text-accent hover:underline"
        >
          {expanded ? t('research.reading.showLess') : t('research.reading.showMore')}
        </button>
      )}
    </section>
  );
}
