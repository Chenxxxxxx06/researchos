'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { createExperiment, listExperiments, listRuns, type Experiment, type ExperimentRun } from '@/lib/api/experiments';
import { ApiError } from '@/lib/api/client';
import { useI18n } from '@/lib/i18n';
import { Skeleton } from '@/components/ui/skeleton';

import { RunDetail } from './RunDetail';
import { ExperimentFlowOverview } from './ExperimentFlowOverview';

const STATUS_COLORS: Record<string, string> = { completed: 'bg-success-bg text-success', running: 'bg-warn-bg text-warn', failed: 'bg-danger-bg text-danger', queued: 'bg-surface-2 text-muted', cancelled: 'bg-surface-2 text-muted' };

export function ExperimentsDashboard({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const [name, setName] = useState('');

  const experiments = useQuery<Experiment[], ApiError>({ queryKey: ['experiments', projectId], queryFn: () => listExperiments(projectId) });
  const create = useMutation({ mutationFn: (v: string) => createExperiment(projectId, { name: v }), onSuccess: () => { setName(''); queryClient.invalidateQueries({ queryKey: ['experiments', projectId] }); } });

  return (
    <div className="-m-6 flex h-[calc(100vh-3rem)]">
      <aside className="w-72 shrink-0 space-y-3 overflow-y-auto border-r border-border bg-surface p-4">
        <h2 className="text-sm font-semibold text-text">{t('experiments.title')}</h2>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(name.trim()); }}>
          <input className="h-9 flex-1 rounded-md border border-border-strong bg-surface px-3 text-xs" placeholder={t('experiments.newExperiment')} value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" disabled={create.isPending || !name.trim()} className="rounded-md bg-accent px-3 text-xs font-medium text-accent-fg hover:bg-accent-hover disabled:opacity-40">{t('common.create')}</button>
        </form>

        {experiments.isLoading && <Skeleton className="h-24" />}
        {experiments.data?.length === 0 && <p className="text-xs text-faint">{t('experiments.empty')}</p>}

        {experiments.data?.map((exp) => (
          <ExperimentItem key={exp.id} projectId={projectId} experiment={exp} selectedRunId={selectedRunId} onSelectRun={setSelectedRunId} />
        ))}
      </aside>

      <main className="flex-1 overflow-y-auto p-6">
        {selectedRunId ? <RunDetail projectId={projectId} runId={selectedRunId} /> : (
          <ExperimentFlowOverview projectId={projectId} />
        )}
      </main>
    </div>
  );
}

function ExperimentItem({ projectId, experiment, selectedRunId, onSelectRun }: { projectId: string; experiment: Experiment; selectedRunId: string | null; onSelectRun: (id: string) => void }) {
  const [open, setOpen] = useState(true);
  const { data, isLoading } = useQuery<ExperimentRun[], ApiError>({
    queryKey: ['exp-runs', projectId, experiment.id],
    queryFn: () => listRuns(projectId, experiment.id),
    enabled: open,
    refetchInterval: (query) =>
      query.state.data?.some((run) => run.status === 'running' || run.status === 'queued')
        ? 3000
        : false,
  });
  return (
    <div className="rounded-lg border border-border bg-surface">
      <button className="flex w-full items-center justify-between px-3 py-2 text-left" onClick={() => setOpen(!open)}>
        <span className="text-xs font-semibold text-text">{experiment.name}</span>
        <span className="text-xs text-faint">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="border-t border-border px-3 py-1">
          {isLoading && <Skeleton className="h-8" />}
          {data?.length === 0 && <p className="text-xs text-faint py-1">No runs</p>}
          {data?.map((run) => (
            <button key={run.id} onClick={() => onSelectRun(run.id)}
              className={`w-full rounded px-2 py-1.5 text-left text-xs ${selectedRunId === run.id ? 'bg-accent text-accent-fg' : 'text-muted hover:bg-surface-2'}`}>
              <div className="flex items-center justify-between">
                <span>{run.name}</span>
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${STATUS_COLORS[run.status] ?? ''}`}>{run.status}</span>
              </div>
              <div className="mt-1 h-1 overflow-hidden rounded-full bg-surface-2">
                <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(0, Math.min(100, run.progress ?? 0))}%` }} />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
