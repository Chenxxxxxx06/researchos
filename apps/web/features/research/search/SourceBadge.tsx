'use client';

import { ExternalLink } from 'lucide-react';

import { provenanceOf, type PaperResult } from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { Badge, type BadgeProps } from '@/components/ui/badge';

const PROVIDER_LABEL: Record<string, string> = {
  arxiv: 'arXiv',
  s2: 'Semantic Scholar',
  openalex: 'OpenAlex',
};

const PROVIDER_VARIANT: Record<string, BadgeProps['variant']> = {
  arxiv: 'danger',
  s2: 'accent',
  openalex: 'success',
};

export function providerLabel(provider: string): string {
  return PROVIDER_LABEL[provider] ?? provider;
}

/**
 * Deduped source badges for a result, with a grouped provenance popover
 * (pure CSS `group-hover` / `group-focus-within` — no dependency). Colors come
 * from semantic token variants, never raw Tailwind hues.
 */
export function SourceBadge({ result }: { result: PaperResult }) {
  const { t } = useI18n();
  const rows = provenanceOf(result);
  const providers = Array.from(new Set(rows.map((r) => r.provider)));

  return (
    <span className="group relative inline-flex" tabIndex={0}>
      <span className="inline-flex flex-wrap items-center gap-1">
        {providers.map((p) => (
          <Badge key={p} size="sm" variant={PROVIDER_VARIANT[p] ?? 'neutral'}>
            {providerLabel(p)}
          </Badge>
        ))}
      </span>

      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-30 mt-1 hidden w-64 flex-col gap-1.5 rounded-md border border-border bg-overlay p-2.5 text-xs shadow-elev2 group-hover:flex group-focus-within:flex"
      >
        <span className="text-[10px] font-semibold uppercase tracking-wide text-faint">
          {t('research.search.provenance')}
        </span>
        {rows.map((r) => (
          <span key={`${r.provider}:${r.external_id}`} className="flex items-center justify-between gap-2">
            <span className="text-muted">{providerLabel(r.provider)}</span>
            {r.url ? (
              <a
                href={r.url}
                target="_blank"
                rel="noreferrer"
                className="pointer-events-auto inline-flex items-center gap-0.5 truncate font-mono text-[10px] text-text hover:underline"
              >
                {r.external_id}
                <ExternalLink className="h-2.5 w-2.5 shrink-0" aria-hidden="true" />
              </a>
            ) : (
              <span className="truncate font-mono text-[10px] text-text">{r.external_id}</span>
            )}
          </span>
        ))}
        {result.doi && (
          <span className="flex items-center justify-between gap-2 border-t border-border pt-1.5">
            <span className="text-muted">DOI</span>
            <span className="truncate font-mono text-[10px] text-text">{result.doi}</span>
          </span>
        )}
        {result.citation_count != null && (
          <span className="text-muted">{t('research.search.citedBy', { n: result.citation_count })}</span>
        )}
      </span>
    </span>
  );
}
