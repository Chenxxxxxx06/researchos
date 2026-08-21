'use client';

import { useQuery } from '@tanstack/react-query';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EvidenceStamp } from '@/components/provenance/EvidenceStamp';
import { ProvenanceTrace } from '@/components/provenance/ProvenanceTrace';
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
  completed: 'bg-success-bg text-success',
  running: 'bg-warn-bg text-warn',
  failed: 'bg-danger-bg text-danger',
  queued: 'bg-surface-2 text-muted',
  cancelled: 'bg-surface-2 text-muted',
};

function StatusBadge({ status }: { status: RunStatus }) {
  const style = STATUS_STYLES[status] ?? 'bg-surface-2 text-muted';
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
  if (isError) return <p className="text-xs text-danger">{t('common.error')}</p>;
  if (!data || data.length === 0)
    return <p className="text-xs text-muted">{t('common.empty')}</p>;

  return (
    <ul className="max-h-48 space-y-0.5 overflow-y-auto font-mono text-[11px]">
      {data.map((log) => (
        <li key={log.seq} className="flex gap-2">
          <span className="shrink-0 uppercase text-faint">{log.level}</span>
          <span className="text-muted">{log.message}</span>
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
  if (isError) return <p className="text-xs text-danger">{t('common.error')}</p>;
  if (!data || data.length === 0)
    return <p className="text-xs text-muted">{t('common.empty')}</p>;

  return (
    <ul className="space-y-1">
      {data.map((artifact) => (
        <li
          key={artifact.id}
          className="flex items-center justify-between rounded border border-border p-2"
        >
          <a
            href={artifact.uri}
            target="_blank"
            rel="noreferrer"
            className="text-xs font-medium text-text underline"
          >
            {artifact.name}
          </a>
          <span className="font-mono text-[10px] text-faint">{artifact.artifact_type}</span>
        </li>
      ))}
    </ul>
  );
}

export function RunDetail({ projectId, runId }: { projectId: string; runId: string }) {
  const { t, locale } = useI18n();
  const zh = locale === 'zh-CN';
  const { data: run, isLoading, isError } = useQuery<ExperimentRun, ApiError>({
    queryKey: ['run', projectId, runId],
    queryFn: () => getRun(projectId, runId),
  });

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError) return <p className="text-sm text-danger">{t('common.error')}</p>;
  if (!run) return <p className="text-sm text-muted">{t('common.empty')}</p>;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="min-w-0">
            <CardTitle>{run.name}</CardTitle>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <EvidenceStamp
                status={run.status}
                tone={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'danger' : run.status === 'running' ? 'accent' : 'neutral'}
                id={run.id.slice(0, 8)}
                date={new Date(run.created_at).toLocaleDateString()}
              />
            </div>
          </div>
          <StatusBadge status={run.status} />
        </CardHeader>
        <CardContent className="space-y-1 text-xs text-muted">
          {run.command && <p className="font-mono text-muted">{run.command}</p>}
          {run.git_commit && <p className="font-mono">{run.git_commit.slice(0, 12)}</p>}
          <ProvenanceTrace
            className="pt-2"
            nodes={[
              { label: zh ? '来源' : 'Source', state: 'done' },
              { label: zh ? '代码' : 'Code', state: run.git_commit ? 'done' : 'todo' },
              { label: zh ? '实验' : 'Run', state: run.status === 'completed' ? 'done' : 'active' },
              { label: zh ? '结论' : 'Claim', state: 'todo' },
            ]}
          />
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
