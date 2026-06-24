import type { Critique } from '@/lib/api/research';

function Section({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-neutral-400">{title}</p>
      <ul className="mt-0.5 space-y-0.5">
        {items.map((item, i) => <li key={i} className="text-[11px] text-neutral-600">• {item}</li>)}
      </ul>
    </div>
  );
}

export function CriticReviewCard({ critique }: { critique: Critique }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-3">
      <p className="text-xs font-semibold text-neutral-800">Critic review</p>
      <p className="mt-1 text-xs leading-relaxed text-neutral-600">{critique.novelty_summary}</p>
      <Section title="Weaknesses" items={critique.weaknesses_json} />
      <Section title="Missing baselines" items={critique.missing_baselines_json} />
      <Section title="Dataset risks" items={critique.dataset_risks_json} />
      <Section title="Reproducibility" items={critique.reproducibility_json} />
      {critique.citations_json.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {critique.citations_json.map((key) => <span key={key} className="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-[10px] text-neutral-600">{key}</span>)}
        </div>
      )}
    </div>
  );
}
