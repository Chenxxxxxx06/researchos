'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, FlaskConical, Plus } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api/client';
import { createExperiment, listExperiments, listRuns, type Experiment, type ExperimentRun } from '@/lib/api/experiments';
import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

import { ExperimentFlowOverview } from './ExperimentFlowOverview';

// Recharts is only needed after a run is selected. Keeping it out of the
// initial experiments chunk makes the primary navigation substantially lighter
// while still giving immediate skeleton feedback on selection.
const RunDetail = dynamic(
  () => import('./RunDetail').then((module) => module.RunDetail),
  { loading: () => <Skeleton className="h-64 w-full" />, ssr: false },
);

const STATUS_VARIANT: Record<string, 'success' | 'warn' | 'danger' | 'neutral' | 'info'> = {
  completed: 'success',
  running: 'warn',
  failed: 'danger',
  queued: 'info',
  cancelled: 'neutral',
};

export function ExperimentsDashboard({ projectId }: { projectId: string }) {
  const { t, locale } = useI18n();
  const zh = locale === 'zh-CN';
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [name, setName] = useState('');
  const queryClient = useQueryClient();
  const experiments = useQuery<Experiment[], ApiError>({
    queryKey: ['experiments', projectId],
    queryFn: () => listExperiments(projectId),
  });
  const create = useMutation({
    mutationFn: (value: string) => createExperiment(projectId, { name: value }),
    onSuccess: () => {
      setName('');
      void queryClient.invalidateQueries({ queryKey: ['experiments', projectId] });
    },
  });

  return (
    <div className="-m-5 flex h-[calc(100dvh-4rem)] min-h-0 lg:-m-6 xl:-m-8">
      <aside className="flex w-[18rem] shrink-0 flex-col border-r border-border bg-surface">
        <header className="workspace-toolbar px-4 py-4">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-accent" aria-hidden="true" />
            <div>
              <h1 className="text-sm font-semibold tracking-[-0.01em] text-text">{t('experiments.title')}</h1>
              <p className="mt-0.5 text-[11px] text-muted">{zh ? '计划、运行与对比' : 'Plans, runs, and comparisons'}</p>
            </div>
          </div>
          <form
            className="mt-4 flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (name.trim()) create.mutate(name.trim());
            }}
          >
            <Input className="h-9 bg-bg text-xs" placeholder={t('experiments.newExperiment')} value={name} onChange={(event) => setName(event.target.value)} />
            <Button type="submit" size="icon" loading={create.isPending} disabled={!name.trim()} aria-label={t('common.create')}>
              <Plus className="h-4 w-4" aria-hidden="true" />
            </Button>
          </form>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {experiments.isLoading && <div className="space-y-2"><Skeleton className="h-24" /><Skeleton className="h-20" /></div>}
          {experiments.isError && <p className="border-l-2 border-danger bg-danger-bg p-3 text-xs leading-5 text-danger">{experiments.error.message}</p>}
          {experiments.data?.length === 0 && <p className="p-3 text-xs leading-5 text-muted">{t('experiments.empty')}</p>}
          <div className="space-y-2">
            {experiments.data?.map((experiment) => (
              <ExperimentItem
                key={experiment.id}
                projectId={projectId}
                experiment={experiment}
                selectedRunId={selectedRunId}
                onSelectRun={setSelectedRunId}
              />
            ))}
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto bg-bg p-5 lg:p-7">
        <div className="mx-auto max-w-[92rem]">
          {selectedRunId ? <RunDetail projectId={projectId} runId={selectedRunId} /> : <ExperimentFlowOverview projectId={projectId} />}
        </div>
      </main>
    </div>
  );
}

function ExperimentItem({ projectId, experiment, selectedRunId, onSelectRun }: { projectId: string; experiment: Experiment; selectedRunId: string | null; onSelectRun: (id: string) => void }) {
  const [open, setOpen] = useState(true);
  const runs = useQuery<ExperimentRun[], ApiError>({
    queryKey: ['exp-runs', projectId, experiment.id],
    queryFn: () => listRuns(projectId, experiment.id),
    enabled: open,
    refetchInterval: (query) => query.state.data?.some((run) => run.status === 'running' || run.status === 'queued') ? 3000 : false,
  });
  const Chevron = open ? ChevronDown : ChevronRight;

  return (
    <section className="overflow-hidden rounded-md border border-border bg-bg">
      <button type="button" className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left hover:bg-surface-2" onClick={() => setOpen((value) => !value)}>
        <span className="truncate text-xs font-semibold text-text">{experiment.name}</span>
        <span className="flex items-center gap-2 text-[10px] text-faint"><span>{runs.data?.length ?? 0}</span><Chevron className="h-3.5 w-3.5" aria-hidden="true" /></span>
      </button>
      {open && (
        <div className="border-t border-border bg-surface p-1.5">
          {runs.isLoading && <Skeleton className="h-10" />}
          {runs.data?.length === 0 && <p className="px-2 py-3 text-[11px] text-muted">No runs</p>}
          {runs.data?.map((run) => {
            const selected = selectedRunId === run.id;
            const progress = run.status === 'completed' ? 100 : Math.max(0, Math.min(100, run.progress ?? 0));
            return (
              <button
                key={run.id}
                type="button"
                onClick={() => onSelectRun(run.id)}
                className={cn(
                  'relative mb-1 w-full overflow-hidden rounded-md px-2.5 py-2 text-left last:mb-0',
                  selected ? 'bg-accent/10 text-text' : 'text-muted hover:bg-surface-2 hover:text-text',
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-xs font-medium">{run.name}</span>
                  <Badge size="sm" variant={STATUS_VARIANT[run.status] ?? 'neutral'}>{run.status}</Badge>
                </div>
                {(run.status === 'running' || run.status === 'queued') && (
                  <div className="absolute inset-x-0 bottom-0 h-0.5 bg-border">
                    <div className="h-full bg-accent transition-[width] duration-500" style={{ width: `${progress}%` }} />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
