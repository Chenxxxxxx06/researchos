import type { Critique } from '@/lib/api/research';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

import { CitationChip } from './CitationChip';

function Section({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2">
      <p className="text-xs font-semibold text-neutral-600">{title}</p>
      <ul className="ml-4 list-disc text-sm text-neutral-700">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export function CriticReviewCard({ critique }: { critique: Critique }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Critic review</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-neutral-800">{critique.novelty_summary}</p>
        <Section title="Weaknesses" items={critique.weaknesses_json} />
        <Section title="Missing baselines" items={critique.missing_baselines_json} />
        <Section title="Dataset risks" items={critique.dataset_risks_json} />
        <Section title="Reproducibility" items={critique.reproducibility_json} />
        {critique.citations_json.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {critique.citations_json.map((key) => (
              <CitationChip key={key} citation={{ label: key }} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
