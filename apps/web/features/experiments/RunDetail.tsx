'use client';

import { useQuery } from '@tanstack/react-query';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  getRun,
  listArtifacts,
  listLogs,
  type Artifact,
  type ExperimentLog,
  type ExperimentRun,
  type RunStatus,
} from '@/lib/api/experiments';
import { ApiError } from '@/lib/api/client';
import { useI18n } from '@/lib/i18n';

import { AnalysisPanel } from './AnalysisPanel';
import { MetricsChart } from './MetricsChart';

const STATUS_STYLES: Record<RunStatus, string> = {
  completed: 'bg-green-100 text-green-700',
  running: 'bg-amber-100 text-amber-700',
  failed: 'bg-red-100 text-red-700',
  queued: 'bg-neutral-100 text-neutral-600',
  cancelled: 'bg-neutral-100 text-neutral-600',
};

function StatusBadge({ status }: { status: RunStatus }) {
  const style = STATUS_STYLES[status] ?? 'bg-neutral-100 text-neutral-600';
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {status}
    </span>
  );
}

function LogsPanel({ projectId, runId }: { projectId: string; runId: string }) {
  const { t } = useI18n();
  const { data, isLoading, isError } = useQuery<ExperimentLog[], ApiError>({
    queryKey: ['logs', projectId, runId],
    queryFn: () => listLogs(projectId, runId),
  });

  if (isLoading) return <Skeleton className="h-16 w-full" />;
  if (isError) return <p className="text-xs text-red-600">{t('common.error')}</p>;
  if (!data || data.length === 0)
    return <p className="text-xs text-neutral-500">{t('common.empty')}</p>;

  return (
    <ul className="max-h-48 space-y-0.5 overflow-y-auto font-mono text-[11px]">
      {data.map((log) => (
        <li key={log.seq} className="flex gap-2">
          <span className="shrink-0 uppercase text-neutral-400">{log.level}</span>
          <span className="text-neutral-700">{log.message}</span>
        </li>
      ))}
    </ul>
  );
}

function ArtifactList({ projectId, runId }: { projectId: string; runId: string }) {
  const { t } = useI18n();
  const { data, isLoading, isError } = useQuery<Artifact[], ApiError>({
    queryKey: ['artifacts', projectId, runId],
    queryFn: () => listArtifacts(projectId, runId),
  });

  if (isLoading) return <Skeleton className="h-16 w-full" />;
  if (isError) return <p className="text-xs text-red-600">{t('common.error')}</p>;
  if (!data || data.length === 0)
    return <p className="text-xs text-neutral-500">{t('common.empty')}</p>;

  return (
    <ul className="space-y-1">
      {data.map((artifact) => (
        <li
          key={artifact.id}
          className="flex items-center justify-between rounded border border-neutral-200 p-2"
        >
          <a
            href={artifact.uri}
            target="_blank"
            rel="noreferrer"
            className="text-xs font-medium text-neutral-800 underline"
          >
            {artifact.name}
          </a>
          <span className="font-mono text-[10px] text-neutral-400">{artifact.artifact_type}</span>
        </li>
      ))}
    </ul>
  );
}

export function RunDetail({ projectId, runId }: { projectId: string; runId: string }) {
  const { t } = useI18n();
  const { data: run, isLoading, isError } = useQuery<ExperimentRun, ApiError>({
    queryKey: ['run', projectId, runId],
    queryFn: () => getRun(projectId, runId),
  });

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError) return <p className="text-sm text-red-600">{t('common.error')}</p>;
  if (!run) return <p className="text-sm text-neutral-500">{t('common.empty')}</p>;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{run.name}</CardTitle>
          <StatusBadge status={run.status} />
        </CardHeader>
        <CardContent className="space-y-1 text-xs text-neutral-500">
          {run.command && <p className="font-mono text-neutral-700">{run.command}</p>}
          {run.git_commit && <p className="font-mono">{run.git_commit.slice(0, 12)}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('experiments.metrics')}</CardTitle>
        </CardHeader>
        <CardContent>
          <MetricsChart projectId={projectId} runId={runId} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('experiments.logs')}</CardTitle>
        </CardHeader>
        <CardContent>
          <LogsPanel projectId={projectId} runId={runId} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('experiments.artifacts')}</CardTitle>
        </CardHeader>
        <CardContent>
          <ArtifactList projectId={projectId} runId={runId} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('experiments.analyze')}</CardTitle>
        </CardHeader>
        <CardContent>
          <AnalysisPanel projectId={projectId} runId={runId} />
        </CardContent>
      </Card>
    </div>
  );
}
