'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { createExperiment, listExperiments, listRuns, type Experiment, type ExperimentRun } from '@/lib/api/experiments';
import { ApiError } from '@/lib/api/client';
import { useI18n } from '@/lib/i18n';
import { Skeleton } from '@/components/ui/skeleton';

import { RunDetail } from './RunDetail';

const STATUS_COLORS: Record<string, string> = { completed: 'bg-emerald-100 text-emerald-700', running: 'bg-amber-100 text-amber-700', failed: 'bg-red-100 text-red-700', queued: 'bg-neutral-100 text-neutral-500', cancelled: 'bg-neutral-100 text-neutral-500' };

export function ExperimentsDashboard({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const [name, setName] = useState('');

  const experiments = useQuery<Experiment[], ApiError>({ queryKey: ['experiments', projectId], queryFn: () => listExperiments(projectId) });
  const create = useMutation({ mutationFn: (v: string) => createExperiment(projectId, { name: v }), onSuccess: () => { setName(''); queryClient.invalidateQueries({ queryKey: ['experiments', projectId] }); } });

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)]">
      <aside className="w-72 shrink-0 space-y-3 overflow-y-auto border-r border-neutral-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-neutral-800">{t('experiments.title')}</h2>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(name.trim()); }}>
          <input className="h-9 flex-1 rounded-lg border border-neutral-300 bg-neutral-50 px-3 text-xs" placeholder={t('experiments.newExperiment')} value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" disabled={create.isPending || !name.trim()} className="rounded-lg bg-neutral-900 px-3 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-40">{t('common.create')}</button>
        </form>

        {experiments.isLoading && <Skeleton className="h-24" />}
        {experiments.data?.length === 0 && <p className="text-xs text-neutral-400">{t('experiments.empty')}</p>}

        {experiments.data?.map((exp) => (
          <ExperimentItem key={exp.id} projectId={projectId} experiment={exp} selectedRunId={selectedRunId} onSelectRun={setSelectedRunId} />
        ))}
      </aside>

      <main className="flex-1 overflow-y-auto p-6">
        {selectedRunId ? <RunDetail projectId={projectId} runId={selectedRunId} /> : (
          <div className="flex h-full items-center justify-center text-sm text-neutral-400">{t('experiments.selectRun')}</div>
        )}
      </main>
    </div>
  );
}

function ExperimentItem({ projectId, experiment, selectedRunId, onSelectRun }: { projectId: string; experiment: Experiment; selectedRunId: string | null; onSelectRun: (id: string) => void }) {
  const [open, setOpen] = useState(true);
  const { data, isLoading } = useQuery<ExperimentRun[], ApiError>({ queryKey: ['exp-runs', projectId, experiment.id], queryFn: () => listRuns(projectId, experiment.id), enabled: open });
  return (
    <div className="rounded-lg border border-neutral-200 bg-white">
      <button className="flex w-full items-center justify-between px-3 py-2 text-left" onClick={() => setOpen(!open)}>
        <span className="text-xs font-semibold text-neutral-800">{experiment.name}</span>
        <span className="text-xs text-neutral-400">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="border-t border-neutral-100 px-3 py-1">
          {isLoading && <Skeleton className="h-8" />}
          {data?.length === 0 && <p className="text-xs text-neutral-400 py-1">No runs</p>}
          {data?.map((run) => (
            <button key={run.id} onClick={() => onSelectRun(run.id)}
              className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-xs ${selectedRunId === run.id ? 'bg-neutral-900 text-white' : 'text-neutral-700 hover:bg-neutral-50'}`}>
              <span>{run.name}</span>
              <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${STATUS_COLORS[run.status] ?? ''}`}>{run.status}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
