'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BarChart3, Code2, Database, Lightbulb, ListOrdered, Sparkles } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { getResearchSynthesis, materializeResearchDirections } from '@/lib/api/knowledge';

export function ResearchSynthesisPanel({ projectId, missionId }: { projectId: string; missionId: string }) {
  const queryClient = useQueryClient();
  const synthesis = useQuery({
    queryKey: ['research-synthesis', projectId, missionId],
    queryFn: () => getResearchSynthesis(projectId, missionId),
    staleTime: 30_000,
  });
  const materialize = useMutation({
    mutationFn: () => materializeResearchDirections(projectId, missionId),
    onSuccess: (data) => {
      queryClient.setQueryData(['research-synthesis', projectId, missionId], data);
      void queryClient.invalidateQueries({ queryKey: ['ideas', projectId] });
    },
  });

  if (synthesis.isLoading) return <div className="h-40 animate-pulse border-b border-border bg-surface-2" />;
  if (synthesis.isError) return <div className="border-b border-danger/20 bg-danger-bg px-6 py-3 text-xs text-danger">{synthesis.error instanceof Error ? synthesis.error.message : 'Unable to build research synthesis.'}</div>;
  const data = synthesis.data;
  if (!data) return null;

  return (
    <section className="border-b border-border bg-surface" aria-labelledby="research-synthesis-title">
      <header className="flex flex-wrap items-start justify-between gap-3 px-5 py-4">
        <div>
          <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-accent" /><h2 id="research-synthesis-title" className="text-sm font-semibold text-text">Evidence-ranked research slate</h2></div>
          <p className="mt-1 text-[11px] text-muted">{data.paper_count} papers · {data.reviewed_card_count} reviewed cards · {data.tuple_count} retrievable tuples</p>
        </div>
        <Button size="sm" variant="secondary" loading={materialize.isPending} disabled={data.directions.length === 0} onClick={() => materialize.mutate()}><ListOrdered className="h-3.5 w-3.5" />Save Top 10 to Ideas</Button>
      </header>
      <div className="grid border-t border-border xl:grid-cols-[minmax(0,1.35fr)_minmax(20rem,0.65fr)]">
        <div className="min-w-0 border-b border-border p-4 xl:border-b-0 xl:border-r">
          <div className="mb-3 flex items-center justify-between"><h3 className="flex items-center gap-2 text-xs font-semibold text-text"><Lightbulb className="h-3.5 w-3.5 text-accent" />Top directions</h3><span className="font-mono text-[9px] text-faint">ABLATION-AWARE SCORE</span></div>
          <div className="grid gap-2 md:grid-cols-2">
            {data.directions.map((direction) => (
              <article key={`${direction.rank}-${direction.title}`} className="border border-border bg-bg p-3">
                <div className="flex items-start gap-3"><span className="font-mono text-lg font-semibold text-accent">{String(direction.rank).padStart(2, '0')}</span><div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-2"><h4 className="text-xs font-semibold leading-5 text-text">{direction.title}</h4><Badge size="sm" variant={direction.evidence_status === 'grounded' ? 'success' : 'warn'}>{direction.score.toFixed(3)}</Badge></div><p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">{direction.hypothesis}</p><div className="mt-2 flex flex-wrap gap-2 font-mono text-[9px] text-faint"><span>{direction.source_paper_ids.length} papers</span><span className="flex items-center gap-1"><Database className="h-2.5 w-2.5" />{direction.benchmarks.length} benchmarks</span><span className="flex items-center gap-1"><BarChart3 className="h-2.5 w-2.5" />{direction.ablation_signals.length} ablations</span><span className="flex items-center gap-1"><Code2 className="h-2.5 w-2.5" />{direction.code_repositories.length} repos</span></div></div></div>
              </article>
            ))}
            {data.directions.length === 0 && <p className="col-span-full py-6 text-center text-xs text-muted">Generate structured reading cards to obtain ranked directions.</p>}
          </div>
        </div>
        <aside className="p-4">
          <div className="mb-3 flex items-center justify-between"><h3 className="flex items-center gap-2 text-xs font-semibold text-text"><Database className="h-3.5 w-3.5 text-info" />Benchmark shortlist</h3><span className="font-mono text-[9px] text-faint">CREDIBILITY</span></div>
          <div className="space-y-2">
            {data.benchmarks.map((benchmark) => <article key={`${benchmark.rank}-${benchmark.name}`} className="border-l-2 border-info bg-info-bg/45 px-3 py-2"><div className="flex items-start justify-between gap-2"><div><p className="text-xs font-semibold text-text">{benchmark.rank}. {benchmark.name}</p><p className="mt-1 text-[10px] text-muted">{benchmark.task}</p></div><span className="font-mono text-[10px] text-info">{benchmark.credibility_score.toFixed(3)}</span></div><p className="mt-2 text-[9px] leading-4 text-faint">{benchmark.reasons.join(' · ')}</p></article>)}
            {data.benchmarks.length === 0 && <p className="py-6 text-center text-xs text-muted">No evidence-backed benchmark has been extracted yet.</p>}
          </div>
        </aside>
      </div>
      {materialize.error instanceof Error && <p className="border-t border-danger/20 bg-danger-bg px-5 py-2 text-xs text-danger">{materialize.error.message}</p>}
    </section>
  );
}
