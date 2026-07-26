'use client';

import { Check, ExternalLink, HelpCircle } from 'lucide-react';
import Link from 'next/link';

import { useI18n } from '@/lib/i18n';
import { Tooltip } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

import type { CitationChipModel } from './citations';

const BASE =
  'inline-flex max-w-[16rem] items-center gap-1 rounded-sm px-1.5 py-0.5 text-[11px] font-medium leading-4 transition-colors';

function truncate(text: string, max = 28): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/**
 * Honest three-state citation chip:
 *   in-library → success dot + title, links to the Reading Room;
 *   external   → neutral, links out, "cited from search" tooltip;
 *   unverified → muted dashed, "could not verify" tooltip.
 */
export function CitationChip({ model, projectId }: { model: CitationChipModel; projectId: string }) {
  const { t } = useI18n();

  if (model.state === 'in-library') {
    return (
      <Tooltip content={truncate(model.title, 60)}>
        <Link
          href={`/projects/${projectId}/research/read/${model.paperId}`}
          className={cn(BASE, 'bg-success-bg text-success hover:opacity-80')}
        >
          <Check className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span className="truncate">{truncate(model.title)}</span>
        </Link>
      </Tooltip>
    );
  }

  if (model.state === 'external') {
    const label = model.title && model.title !== model.key ? truncate(model.title) : model.key;
    const inner = (
      <span className={cn(BASE, 'bg-surface-2 text-muted', model.url && 'hover:text-text')}>
        <span className="truncate">{label}</span>
        {model.url && <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />}
      </span>
    );
    return (
      <Tooltip content={t('research.chat.externalSource')}>
        {model.url ? (
          <a href={model.url} target="_blank" rel="noreferrer" className="inline-flex">
            {inner}
          </a>
        ) : (
          inner
        )}
      </Tooltip>
    );
  }

  return (
    <Tooltip content={t('research.chat.unverified')}>
      <span className={cn(BASE, 'border border-dashed border-border-strong font-mono text-faint')}>
        <HelpCircle className="h-3 w-3 shrink-0" aria-hidden="true" />
        <span className="truncate">{model.key}</span>
      </span>
    </Tooltip>
  );
}
