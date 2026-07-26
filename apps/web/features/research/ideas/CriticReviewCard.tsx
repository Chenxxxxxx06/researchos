'use client';

import type { Critique } from '@/lib/api/ideas';
import { useI18n, type DictKey } from '@/lib/i18n';

import { CitationChip } from '../CitationChip';
import { resolveCitation, type LibraryMap } from '../citations';

function Section({ titleKey, items }: { titleKey: DictKey; items: string[] }) {
  const { t } = useI18n();
  if (items.length === 0) return null;
  return (
    <div className="mt-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">{t(titleKey)}</p>
      <ul className="mt-0.5 space-y-0.5">
        {items.map((item, i) => (
          <li key={i} className="text-[11px] leading-relaxed text-muted">
            • {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Critic review, tokenized + i18n'd, with citation-integrity chips (D8.2). */
export function CriticReviewCard({
  critique,
  projectId,
  library,
}: {
  critique: Critique;
  projectId: string;
  library: LibraryMap;
}) {
  const { t } = useI18n();
  return (
    <div className="rounded-lg border border-border bg-surface-2 p-3">
      <p className="text-xs font-semibold text-text">{t('research.critic.title')}</p>
      {critique.novelty_summary && (
        <p className="mt-1 text-xs leading-relaxed text-muted">{critique.novelty_summary}</p>
      )}
      <Section titleKey="research.critic.weaknesses" items={critique.weaknesses_json} />
      <Section titleKey="research.critic.missingBaselines" items={critique.missing_baselines_json} />
      <Section titleKey="research.critic.datasetRisks" items={critique.dataset_risks_json} />
      <Section titleKey="research.critic.reproducibility" items={critique.reproducibility_json} />
      {critique.citations_json.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {critique.citations_json.map((key) => (
            <CitationChip key={key} projectId={projectId} model={resolveCitation(key, [], library)} />
          ))}
        </div>
      )}
    </div>
  );
}
