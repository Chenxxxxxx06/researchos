'use client';

import { useEffect, useState } from 'react';

import type { PaperSection, SectionKind } from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

/** Short kind markers (D5.3) — a compact mono glyph per section kind. */
const KIND_GLYPH: Record<SectionKind, string> = {
  abstract: 'A',
  introduction: 'I',
  background: 'B',
  method: 'M',
  experiments: 'E',
  results: 'R',
  related_work: 'W',
  conclusion: 'C',
  appendix: 'P',
  other: '·',
};

/**
 * Sticky clickable outline (D5.3). Click scrolls the matching section into view;
 * an IntersectionObserver highlights the active section as the reader scrolls
 * (the click-to-scroll path is the MUST; the observer is the SHOULD enhancement).
 */
export function SectionOutline({ sections }: { sections: PaperSection[] }) {
  const { t } = useI18n();
  const [activeSeq, setActiveSeq] = useState<number | null>(sections[0]?.seq ?? null);

  useEffect(() => {
    if (sections.length === 0 || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) {
          const seq = Number(visible[0].target.getAttribute('data-seq'));
          if (!Number.isNaN(seq)) setActiveSeq(seq);
        }
      },
      { rootMargin: '0px 0px -70% 0px', threshold: 0 },
    );
    for (const s of sections) {
      const el = document.getElementById(`sec-${s.seq}`);
      if (el) {
        el.setAttribute('data-seq', String(s.seq));
        observer.observe(el);
      }
    }
    return () => observer.disconnect();
  }, [sections]);

  const scrollTo = (seq: number) => {
    setActiveSeq(seq);
    document.getElementById(`sec-${seq}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <nav aria-label={t('research.reading.outline')} className="sticky top-0 w-56 shrink-0 self-start">
      <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wide text-faint">
        {t('research.reading.outline')}
      </p>
      <ul className="max-h-[calc(100vh-10rem)] space-y-0.5 overflow-y-auto">
        {sections.map((s) => {
          const active = s.seq === activeSeq;
          return (
            <li key={s.seq}>
              <button
                type="button"
                onClick={() => scrollTo(s.seq)}
                aria-current={active ? 'true' : undefined}
                style={{ paddingLeft: `${0.5 + Math.max(0, s.level - 1) * 0.75}rem` }}
                className={cn(
                  'flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-[11px] transition-colors',
                  active ? 'bg-surface-2 font-medium text-text' : 'text-muted hover:bg-surface-2 hover:text-text',
                )}
              >
                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-sm bg-surface-2 font-mono text-[9px] text-faint">
                  {KIND_GLYPH[s.kind] ?? '·'}
                </span>
                <span className="truncate">{s.heading}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
