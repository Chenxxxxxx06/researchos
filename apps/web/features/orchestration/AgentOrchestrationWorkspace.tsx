'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Bot,
  Check,
  CheckCircle2,
  Clock3,
  FileCheck2,
  GitFork,
  Network,
  Play,
  RefreshCw,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { Badge, type BadgeProps } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { listMissions } from '@/lib/api/missions';
import {
  bootstrapOrchestrationGraph,
  decideApprovalGate,
  dispatchMissionTask,
  getOrchestrationGraph,
  tickOrchestration,
  type ApprovalGate,
  type MissionTask,
  type MissionTaskStatus,
  type OrchestrationGraph,
} from '@/lib/api/orchestration';
import { cn } from '@/lib/utils';

import { ResearchLoopWorkbench } from './ResearchLoopWorkbench';

const LANES: Array<{ title: string; keys: string[] }> = [
  {
    title: 'EVIDENCE & DIRECTION',
    keys: ['scope', 'discover', 'read', 'synthesize', 'gap', 'critic', 'direction'],
  },
  {
    title: 'REPOSITORY & BUILD',
    keys: ['repository', 'baseline', 'coding', 'experiment_plan'],
  },
  { title: 'EXPERIMENT & ANALYSIS', keys: ['experiment_run', 'reproduce', 'analyze'] },
  { title: 'WRITE & RELEASE', keys: ['write', 'review', 'release'] },
];

const STATUS: Record<MissionTaskStatus, { label: string; variant: BadgeProps['variant'] }> = {
  draft: { label: 'Blocked', variant: 'neutral' },
  ready: { label: 'Ready', variant: 'info' },
  leased: { label: 'Leased', variant: 'accent' },
  running: { label: 'Running', variant: 'accent' },
  artifact_ready: { label: 'Artifact ready', variant: 'info' },
  waiting_approval: { label: 'Approval', variant: 'warn' },
  completed: { label: 'Completed', variant: 'success' },
  retryable_failed: { label: 'Retry queued', variant: 'warn' },
  terminal_failed: { label: 'Failed', variant: 'danger' },
  cancelled: { label: 'Cancelled', variant: 'outline' },
};

export function AgentOrchestrationWorkspace({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [missionId, setMissionId] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [contextText, setContextText] = useState('{}');
  const [contextError, setContextError] = useState<string | null>(null);

  const missions = useQuery({
    queryKey: ['missions', projectId, 'orchestration'],
    queryFn: () => listMissions(projectId),
  });
  useEffect(() => {
    if (!missionId && missions.data?.items[0]) setMissionId(missions.data.items[0].id);
  }, [missionId, missions.data]);

  const graph = useQuery({
    queryKey: ['orchestration-graph', projectId, missionId],
    queryFn: () => getOrchestrationGraph(projectId, missionId as string),
    enabled: Boolean(missionId),
    refetchInterval: (query) =>
      (query.state.data as OrchestrationGraph | undefined)?.tasks.some((task) =>
        ['leased', 'running'].includes(task.status),
      )
        ? 5000
        : false,
  });

  const selectedTask = graph.data?.tasks.find((task) => task.id === selectedTaskId) ?? null;
  const selectedMission = missions.data?.items.find((mission) => mission.id === missionId);

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: ['orchestration-graph', projectId, missionId],
    });
  const bootstrap = useMutation({
    mutationFn: () => bootstrapOrchestrationGraph(projectId, missionId as string),
    onSuccess: (data) =>
      queryClient.setQueryData(['orchestration-graph', projectId, missionId], data),
  });
  const tick = useMutation({
    mutationFn: () => tickOrchestration(projectId, missionId as string),
    onSuccess: (data) =>
      queryClient.setQueryData(['orchestration-graph', projectId, missionId], data.graph),
  });
  const gateDecision = useMutation({
    mutationFn: ({ gate, decision }: { gate: ApprovalGate; decision: 'approve' | 'reject' }) =>
      decideApprovalGate(projectId, gate.id, decision),
    onSuccess: () => void invalidate(),
  });
  const dispatch = useMutation({
    mutationFn: ({ task, context }: { task: MissionTask; context: Record<string, unknown> }) =>
      dispatchMissionTask(projectId, task.id, message.trim(), context),
    onSuccess: () => {
      setContextError(null);
      void invalidate();
    },
  });

  const dependencies = useMemo(() => {
    const tasks = new Map((graph.data?.tasks ?? []).map((task) => [task.id, task.task_key]));
    const result = new Map<string, string[]>();
    for (const edge of graph.data?.dependencies ?? []) {
      const parent = tasks.get(edge.depends_on_task_id);
      if (parent) result.set(edge.task_id, [...(result.get(edge.task_id) ?? []), parent]);
    }
    return result;
  }, [graph.data]);

  const openTask = (task: MissionTask) => {
    setSelectedTaskId(task.id);
    setMessage(
      `Execute "${task.title}" for mission "${selectedMission?.topic ?? ''}". ` +
        'Inspect existing artifacts first, satisfy the task acceptance criteria, and return only verifiable outputs.',
    );
    setContextText(JSON.stringify(task.input_json, null, 2));
    setContextError(null);
  };

  const submitDispatch = () => {
    if (!selectedTask) return;
    try {
      const parsed = JSON.parse(contextText) as unknown;
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error();
      dispatch.mutate({ task: selectedTask, context: parsed as Record<string, unknown> });
    } catch {
      setContextError('Context 必须是 JSON 对象。');
    }
  };

  if (missions.isLoading) return <Skeleton className="h-[32rem] w-full" />;
  if (!missions.data?.items.length) {
    return (
      <EmptyState
        icon={Network}
        title="还没有 Research Mission"
        body="先创建一个持久化科研任务，再初始化内部 Agent DAG。"
        actions={
          <Button onClick={() => location.assign(`/projects/${projectId}/missions`)}>
            创建 Mission
          </Button>
        }
      />
    );
  }

  return (
    <div className="-m-6 min-h-[calc(100vh-3.5rem)] bg-bg lg:-m-8">
      <header className="border-b border-border bg-surface px-6 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="flex items-center gap-2 text-lg font-semibold text-text">
              <Network className="h-5 w-5 text-accent" /> Mission Control
            </h1>
            <p className="mt-1 truncate text-xs text-muted">
              {selectedMission?.objective || selectedMission?.topic}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={missionId ?? ''}
              onChange={(event) => {
                setMissionId(event.target.value);
                setSelectedTaskId(null);
              }}
              className="h-8 max-w-72 rounded-md border border-border-strong bg-bg px-2 text-xs text-text"
            >
              {missions.data.items.map((mission) => (
                <option key={mission.id} value={mission.id}>
                  {mission.topic}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              variant="secondary"
              loading={tick.isPending}
              disabled={!graph.data?.tasks.length}
              onClick={() => tick.mutate()}
            >
              <RefreshCw className="h-3.5 w-3.5" /> Reconcile
            </Button>
          </div>
        </div>
      </header>

      {!graph.isLoading && graph.data?.tasks.length === 0 && (
        <section className="border-b border-border bg-info-bg px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-info">该 Mission 尚未创建内部任务图</p>
              <p className="mt-1 text-xs text-muted">17 个节点 · 16 条依赖 · 6 个强制审批 Gate</p>
            </div>
            <Button loading={bootstrap.isPending} onClick={() => bootstrap.mutate()}>
              <GitFork className="h-4 w-4" /> 初始化 DAG
            </Button>
          </div>
        </section>
      )}

      {graph.data && graph.data.tasks.length > 0 && (
        <>
          <section className="grid grid-cols-2 border-b border-border bg-surface md:grid-cols-5">
            <Metric label="TOTAL" value={graph.data.tasks.length} />
            <Metric label="READY" value={graph.data.counts.ready ?? 0} tone="info" />
            <Metric
              label="RUNNING"
              value={(graph.data.counts.running ?? 0) + (graph.data.counts.leased ?? 0)}
              tone="accent"
            />
            <Metric
              label="APPROVAL"
              value={graph.data.counts.waiting_approval ?? 0}
              tone="warn"
            />
            <Metric
              label="ARTIFACTS"
              value={graph.data.artifacts.length}
              tone="success"
            />
          </section>

          {missionId && (
            <ResearchLoopWorkbench
              projectId={projectId}
              missionId={missionId}
              experimentTaskReady={
                graph.data.tasks.find((task) => task.task_key === 'experiment_run')?.status ===
                'ready'
              }
            />
          )}

          <main className="grid min-h-[40rem] xl:grid-cols-[minmax(0,1fr)_21rem]">
            <div className="min-w-0 border-r border-border">
              {LANES.map((lane) => {
                const tasks = lane.keys
                  .map((key) => graph.data.tasks.find((task) => task.task_key === key))
                  .filter((task): task is MissionTask => Boolean(task));
                return (
                  <section key={lane.title} className="border-b border-border px-5 py-4">
                    <h2 className="text-[10px] font-semibold tracking-[0.16em] text-faint">
                      {lane.title}
                    </h2>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2 2xl:grid-cols-4">
                      {tasks.map((task) => (
                        <TaskTile
                          key={task.id}
                          task={task}
                          dependencies={dependencies.get(task.id) ?? []}
                          artifactCount={
                            graph.data.artifacts.filter((item) => item.task_id === task.id).length
                          }
                          selected={selectedTaskId === task.id}
                          onClick={() => openTask(task)}
                        />
                      ))}
                    </div>
                  </section>
                );
              })}
            </div>

            <aside className="bg-surface">
              <section className="border-b border-border p-4">
                <h2 className="flex items-center gap-2 text-xs font-semibold text-text">
                  <ShieldCheck className="h-4 w-4 text-warn" /> Approval Gates
                </h2>
                <div className="mt-3 space-y-2">
                  {graph.data.gates.map((gate) => {
                    const task = graph.data.tasks.find((item) => item.id === gate.task_id);
                    return (
                      <div key={gate.id} className="border-b border-border pb-2 last:border-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-medium text-text">
                            {gate.gate_kind}
                          </span>
                          <Badge
                            size="sm"
                            variant={
                              gate.status === 'approved'
                                ? 'success'
                                : gate.status === 'rejected'
                                  ? 'danger'
                                  : 'warn'
                            }
                          >
                            {gate.status}
                          </Badge>
                        </div>
                        <p className="mt-0.5 truncate text-[10px] text-faint">{task?.title}</p>
                        {gate.status === 'pending' && task?.status === 'waiting_approval' && (
                          <div className="mt-2 flex gap-1">
                            <Button
                              size="sm"
                              className="h-6 px-2 text-[10px]"
                              loading={
                                gateDecision.isPending && gateDecision.variables?.gate.id === gate.id
                              }
                              onClick={() => gateDecision.mutate({ gate, decision: 'approve' })}
                            >
                              <Check className="h-3 w-3" /> Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 px-2 text-[10px] text-danger"
                              onClick={() => gateDecision.mutate({ gate, decision: 'reject' })}
                            >
                              <X className="h-3 w-3" /> Reject
                            </Button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                {gateDecision.error instanceof Error && (
                  <p className="mt-2 text-[10px] text-danger">{gateDecision.error.message}</p>
                )}
              </section>

              <section className="p-4">
                <h2 className="flex items-center gap-2 text-xs font-semibold text-text">
                  <FileCheck2 className="h-4 w-4 text-success" /> Artifact Registry
                </h2>
                <div className="mt-3 space-y-2">
                  {graph.data.artifacts.slice(0, 12).map((artifact) => (
                    <div
                      key={artifact.id}
                      className="min-w-0 border-b border-border pb-2 text-[10px] last:border-0"
                    >
                      <p className="truncate font-medium text-text">
                        {artifact.schema_name}/v{artifact.schema_version}
                      </p>
                      <p className="mt-0.5 truncate font-mono text-faint">
                        {artifact.content_hash.slice(0, 16)}
                      </p>
                    </div>
                  ))}
                  {graph.data.artifacts.length === 0 && (
                    <p className="text-[10px] text-faint">No artifacts</p>
                  )}
                </div>
              </section>
              <section className="border-t border-border p-4">
                <h2 className="flex items-center gap-2 text-xs font-semibold text-text">
                  <Clock3 className="h-4 w-4 text-info" /> Task Events
                </h2>
                <div className="mt-3 space-y-2">
                  {graph.data.events.slice(0, 10).map((event) => (
                    <div key={event.id} className="border-b border-border pb-2 text-[10px] last:border-0">
                      <p className="truncate font-medium text-text">{event.event_type}</p>
                      <p className="mt-0.5 text-faint">
                        {new Date(event.created_at).toLocaleTimeString()}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            </aside>
          </main>
        </>
      )}

      {selectedTask && (
        <section className="sticky bottom-0 border-t border-border bg-overlay px-5 py-4 shadow-elev3">
          <div className="grid gap-3 xl:grid-cols-[minmax(16rem,0.7fr)_minmax(20rem,1fr)_minmax(18rem,0.8fr)_auto]">
            <div>
              <p className="text-xs font-semibold text-text">{selectedTask.title}</p>
              <p className="mt-1 font-mono text-[10px] text-faint">
                {selectedTask.idempotency_key}
              </p>
              {selectedTask.agent_run_id && (
                <p className="mt-1 text-[10px] text-accent">
                  Run {selectedTask.agent_run_id.slice(0, 8)}
                </p>
              )}
            </div>
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={3}
              className="w-full rounded-md border border-border-strong bg-bg p-2 text-[11px] text-text"
              aria-label="Agent task message"
            />
            <div>
              <textarea
                value={contextText}
                onChange={(event) => setContextText(event.target.value)}
                rows={3}
                className="w-full rounded-md border border-border-strong bg-bg p-2 font-mono text-[10px] text-text"
                aria-label="Agent context JSON"
              />
              {contextError && <p className="mt-1 text-[10px] text-danger">{contextError}</p>}
            </div>
            <Button
              className="self-end"
              loading={dispatch.isPending}
              disabled={
                selectedTask.status !== 'ready' ||
                !selectedTask.agent_type ||
                !message.trim()
              }
              onClick={submitDispatch}
            >
              <Play className="h-4 w-4" /> Dispatch
            </Button>
          </div>
          {dispatch.error instanceof Error && (
            <p className="mt-2 text-[10px] text-danger">{dispatch.error.message}</p>
          )}
        </section>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: number;
  tone?: 'neutral' | 'info' | 'accent' | 'warn' | 'success';
}) {
  const colors = {
    neutral: 'text-text',
    info: 'text-info',
    accent: 'text-accent',
    warn: 'text-warn',
    success: 'text-success',
  };
  return (
    <div className="border-r border-border px-5 py-3 last:border-r-0">
      <p className="text-[9px] font-semibold tracking-[0.14em] text-faint">{label}</p>
      <p className={cn('mt-1 text-xl font-semibold', colors[tone])}>{value}</p>
    </div>
  );
}

function TaskTile({
  task,
  dependencies,
  artifactCount,
  selected,
  onClick,
}: {
  task: MissionTask;
  dependencies: string[];
  artifactCount: number;
  selected: boolean;
  onClick: () => void;
}) {
  const Icon =
    task.status === 'completed'
      ? CheckCircle2
      : task.status === 'terminal_failed'
        ? AlertTriangle
        : task.status === 'waiting_approval'
          ? ShieldCheck
          : task.status === 'running'
            ? Bot
            : Clock3;
  const status = STATUS[task.status];
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'min-h-28 rounded-md border bg-surface p-3 text-left transition-colors',
        selected
          ? 'border-accent ring-1 ring-accent/30'
          : 'border-border hover:border-border-strong',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <Icon className="h-4 w-4 shrink-0 text-muted" />
        <Badge size="sm" variant={status.variant}>
          {status.label}
        </Badge>
      </div>
      <p className="mt-2 text-xs font-medium leading-4 text-text">{task.title}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[9px] text-faint">
        <span>{task.role}</span>
        <span>
          {task.attempt}/{task.max_attempts}
        </span>
        {artifactCount > 0 && <span>{artifactCount} artifact</span>}
      </div>
      {dependencies.length > 0 && (
        <p className="mt-1 truncate font-mono text-[9px] text-faint">
          {'<-'} {dependencies.join(', ')}
        </p>
      )}
    </button>
  );
}
