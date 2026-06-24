'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  createExperiment,
  listExperiments,
  listRuns,
  type Experiment,
  type ExperimentRun,
} from '@/lib/api/experiments';
import { ApiError } from '@/lib/api/client';
import { useI18n } from '@/lib/i18n';

import { RunDetail } from './RunDetail';

function RunsList({
  projectId,
  experimentId,
  selectedRunId,
  onSelect,
}: {
  projectId: string;
  experimentId: string;
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
}) {
  const { t } = useI18n();
  const { data, isLoading, isError } = useQuery<ExperimentRun[], ApiError>({
    queryKey: ['exp-runs', projectId, experimentId],
    queryFn: () => listRuns(projectId, experimentId),
  });

  if (isLoading) return <Skeleton className="h-12 w-full" />;
  if (isError) return <p className="text-xs text-red-600">{t('common.error')}</p>;
  if (!data || data.length === 0)
    return <p className="text-xs text-neutral-500">{t('experiments.noRuns')}</p>;

  return (
    <ul className="space-y-1">
      {data.map((run) => (
        <li key={run.id}>
          <button
            type="button"
            onClick={() => onSelect(run.id)}
            className={`flex w-full items-center justify-between rounded px-2 py-1 text-left text-xs ${
              selectedRunId === run.id
                ? 'bg-neutral-900 text-white'
                : 'text-neutral-700 hover:bg-neutral-100'
            }`}
          >
            <span className="truncate">{run.name}</span>
            <span className="ml-2 shrink-0 font-mono text-[10px] opacity-70">{run.status}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function ExperimentItem({
  projectId,
  experiment,
  selectedRunId,
  onSelectRun,
}: {
  projectId: string;
  experiment: Experiment;
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="rounded-md border border-neutral-200 p-2">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <span className="text-sm font-medium text-neutral-900">{experiment.name}</span>
        <span className="text-xs text-neutral-400">{expanded ? '−' : '+'}</span>
      </button>
      {experiment.goal && <p className="mt-0.5 text-xs text-neutral-500">{experiment.goal}</p>}
      {expanded && (
        <div className="mt-2">
          <RunsList
            projectId={projectId}
            experimentId={experiment.id}
            selectedRunId={selectedRunId}
            onSelect={onSelectRun}
          />
        </div>
      )}
    </div>
  );
}

function NewExperimentForm({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [name, setName] = useState('');

  const mutation = useMutation<Experiment, ApiError, string>({
    mutationFn: (value) => createExperiment(projectId, { name: value }),
    onSuccess: () => {
      setName('');
      queryClient.invalidateQueries({ queryKey: ['experiments', projectId] });
    },
  });

  return (
    <form
      className="flex gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) mutation.mutate(name.trim());
      }}
    >
      <Input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={t('common.name')}
      />
      <Button type="submit" size="sm" disabled={mutation.isPending || !name.trim()}>
        {t('common.create')}
      </Button>
    </form>
  );
}

export function ExperimentsDashboard({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery<Experiment[], ApiError>({
    queryKey: ['experiments', projectId],
    queryFn: () => listExperiments(projectId),
  });

  return (
    <div className="grid h-[calc(100vh-7rem)] grid-cols-12 gap-4">
      <aside className="col-span-4 space-y-3 overflow-y-auto">
        <Card>
          <CardHeader>
            <CardTitle>{t('experiments.newExperiment')}</CardTitle>
          </CardHeader>
          <CardContent>
            <NewExperimentForm projectId={projectId} />
          </CardContent>
        </Card>

        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {t('experiments.title')}
          </h3>
          {isLoading && <Skeleton className="h-24 w-full" />}
          {isError && <p className="text-xs text-red-600">{t('common.error')}</p>}
          {!isLoading && !isError && (!data || data.length === 0) && (
            <p className="text-xs text-neutral-500">{t('experiments.empty')}</p>
          )}
          {data?.map((experiment) => (
            <ExperimentItem
              key={experiment.id}
              projectId={projectId}
              experiment={experiment}
              selectedRunId={selectedRunId}
              onSelectRun={setSelectedRunId}
            />
          ))}
        </div>
      </aside>

      <section className="col-span-8 overflow-y-auto">
        {selectedRunId ? (
          <RunDetail projectId={projectId} runId={selectedRunId} />
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-neutral-500">{t('experiments.selectRun')}</p>
          </div>
        )}
      </section>
    </div>
  );
}
