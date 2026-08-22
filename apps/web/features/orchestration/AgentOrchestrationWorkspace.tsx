'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  Check,
  Clock3,
  FileCheck2,
  GitFork,
  Network,
  Play,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { listMissions } from '@/lib/api/missions';
import {
  bootstrapOrchestrationGraph,
  decideApprovalGate,
  dispatchMissionTask,
  getOrchestrationGraph,
  startAutopilot,
  tickOrchestration,
  type ApprovalGate,
  type MissionTask,
  type OrchestrationGraph,
} from '@/lib/api/orchestration';
import { cn } from '@/lib/utils';

import { AgentCapabilityLedger } from './AgentCapabilityLedger';
import { MissionGraph, TASK_STATUS } from './MissionGraph';
import { ResearchLoopWorkbench } from './ResearchLoopWorkbench';
import { ResearchSynthesisPanel } from './ResearchSynthesisPanel';

type InspectorTab = 'task' | 'gates' | 'artifacts' | 'events';

export function AgentOrchestrationWorkspace({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [missionId, setMissionId] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>('task');
  const [message, setMessage] = useState('');
  const [contextText, setContextText] = useState('{}');
  const [contextError, setContextError] = useState<string | null>(null);
  const [venue, setVenue] = useState('generic');
  const [allowLocalPilot, setAllowLocalPilot] = useState(false);
  const [autopilotMessage, setAutopilotMessage] = useState<string | null>(null);

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
        ? 1500
        : false,
  });

  const selectedTask = graph.data?.tasks.find((task) => task.id === selectedTaskId) ?? null;
  const selectedMission = missions.data?.items.find((mission) => mission.id === missionId);
  const completed = graph.data?.progress.completed_tasks ?? graph.data?.counts.completed ?? 0;
  const taskCount = graph.data?.progress.total_tasks ?? graph.data?.tasks.length ?? 0;
  const progress = graph.data?.progress.progress_percent ?? (taskCount ? Math.round((completed / taskCount) * 100) : 0);

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
  const autopilot = useMutation({
    mutationFn: () => startAutopilot(projectId, missionId as string, {
      venue,
      auto_apply_code: allowLocalPilot,
      isolated_workspace_confirmed: true,
      max_directions: 10,
      pilot_first: true,
      allow_paid_compute: false,
      allow_trusted_local_execution: allowLocalPilot,
    }),
    onSuccess: (data) => {
      queryClient.setQueryData(['orchestration-graph', projectId, missionId], data.graph);
      setAutopilotMessage(data.blockers.length ? `${data.next_action} · ${data.blockers.join(' · ')}` : data.next_action);
    },
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
    setInspectorTab('task');
    setMessage(
      `Execute "${task.title}" for mission "${selectedMission?.topic ?? ''}". ` +
        'Inspect existing artifacts first, satisfy the acceptance criteria, and return only verifiable outputs.',
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
    <div className="-m-5 min-h-[calc(100vh-4rem)] overflow-x-hidden bg-bg lg:-m-6 xl:-m-8">
      <header className="mission-grid border-b border-border px-5 py-5 sm:px-7 sm:py-6">
        <div className="mx-auto max-w-[112rem]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 max-w-3xl">
              <div className="flex items-center gap-2 font-mono text-[10px] uppercase text-muted">
                <Network className="h-3.5 w-3.5 text-accent" /> Autonomous research system
                <span className="h-1 w-1 rounded-full bg-success" /> live graph
              </div>
              <h1 className="mt-2 text-xl font-semibold text-text sm:text-2xl">Mission Control</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                {selectedMission?.objective || selectedMission?.topic}
              </p>
            </div>
            <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
              <label className="min-w-0 flex-1 sm:w-72 sm:flex-none">
                <span className="sr-only">Mission</span>
                <select
                  value={missionId ?? ''}
                  onChange={(event) => {
                    setMissionId(event.target.value);
                    setSelectedTaskId(null);
                    setInspectorTab('task');
                  }}
                  className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-xs text-text shadow-elev1"
                >
                  {missions.data.items.map((mission) => (
                    <option key={mission.id} value={mission.id}>
                      {mission.topic}
                    </option>
                  ))}
                </select>
              </label>
              <input value={venue} onChange={(event) => setVenue(event.target.value)} aria-label="Target venue" className="h-9 w-28 rounded-md border border-border-strong bg-surface px-2 text-xs text-text" placeholder="venue" />
              <label className="flex h-9 items-center gap-1.5 border border-border bg-surface px-2 text-[10px] text-muted"><input type="checkbox" checked={allowLocalPilot} onChange={(event) => setAllowLocalPilot(event.target.checked)} />trusted auto-code + pilot</label>
              <Button size="sm" loading={autopilot.isPending} disabled={!missionId} onClick={() => autopilot.mutate()}>
                <Rocket className="h-3.5 w-3.5" /> Start / continue autopilot
              </Button>
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

          {(autopilotMessage || autopilot.error) && <div className={`mt-4 border-l-2 px-3 py-2 text-xs ${autopilot.error ? 'border-danger bg-danger-bg text-danger' : 'border-info bg-info-bg text-info'}`}>{autopilot.error instanceof Error ? autopilot.error.message : autopilotMessage}</div>}
          {taskCount > 0 && (
            <div className="mt-6 grid grid-cols-2 gap-x-0 gap-y-4 border-t border-border pt-4 sm:grid-cols-4 lg:grid-cols-[minmax(15rem,1fr)_repeat(4,minmax(6rem,8rem))]">
              <div className="col-span-2 min-w-0 pb-1 sm:col-span-4 lg:col-span-1 lg:pb-0">
                <div className="flex items-center justify-between text-[11px] text-muted">
                  <span>Mission completion</span>
                  <span className="font-mono tabular-nums text-text">{progress}%</span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-sm bg-surface-2">
                  <div
                    className="h-full bg-accent transition-[width] duration-500"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
              <Metric label="Ready" value={graph.data?.counts.ready ?? 0} tone="info" />
              <Metric
                label="Running"
                value={(graph.data?.counts.running ?? 0) + (graph.data?.counts.leased ?? 0)}
                tone="accent"
              />
              <Metric label="Gates" value={graph.data?.counts.waiting_approval ?? 0} tone="warn" />
              <Metric label="Artifacts" value={graph.data?.artifacts.length ?? 0} tone="success" />
            </div>
          )}
        </div>
      </header>

      {(graph.data?.progress.active_agents.length ?? 0) > 0 && (
        <section className="border-b border-border bg-surface px-5 py-3 sm:px-7">
          <div className="mx-auto max-w-[112rem]"><div className="mb-2 flex items-center justify-between"><h2 className="text-[10px] font-semibold uppercase tracking-wide text-muted">Agents working now</h2><span className="font-mono text-[9px] text-faint">phase {graph.data?.progress.current_phase}</span></div><div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">{graph.data?.progress.active_agents.map((agent) => <article key={agent.task_id} className="border border-accent/25 bg-accent/5 px-3 py-2"><div className="flex items-center justify-between gap-2"><p className="text-xs font-semibold text-text">{agent.role}</p><Badge size="sm" variant="accent" dot>{agent.status}</Badge></div><p className="mt-1 line-clamp-2 text-[10px] text-muted">{agent.current_action}</p><p className="mt-2 font-mono text-[9px] text-faint">{agent.agent_type} · attempt {agent.attempt}</p></article>)}</div></div>
        </section>
      )}

      {!graph.isLoading && graph.data?.tasks.length === 0 && (
        <section className="border-b border-border bg-info-bg px-6 py-5">
          <div className="mx-auto flex max-w-[112rem] flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-info">该 Mission 尚未创建内部任务图</p>
              <p className="mt-1 text-xs text-muted">26 个 typed 节点 · Pilot-first 长程循环 · 凭证/仓库/算力/发布 Gate</p>
            </div>
            <Button loading={bootstrap.isPending} onClick={() => bootstrap.mutate()}>
              <GitFork className="h-4 w-4" /> 初始化 DAG
            </Button>
          </div>
        </section>
      )}

      {graph.isLoading && <Skeleton className="m-6 h-[36rem] lg:m-8" />}

      {graph.data && graph.data.tasks.length > 0 && (
        <div className="mx-auto max-w-[112rem]">
          <AgentCapabilityLedger projectId={projectId} />
          {missionId && <ResearchSynthesisPanel projectId={projectId} missionId={missionId} />}
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

          <main className="grid min-h-[44rem] xl:grid-cols-[minmax(0,1fr)_23rem]">
            <div className="min-w-0 border-b border-border xl:border-b-0 xl:border-r">
              <MissionGraph
                tasks={graph.data.tasks}
                dependencies={dependencies}
                artifacts={graph.data.artifacts}
                selectedTaskId={selectedTaskId}
                onSelect={openTask}
              />
            </div>

            <Inspector
              graph={graph.data}
              selectedTask={selectedTask}
              tab={inspectorTab}
              onTabChange={(value) => setInspectorTab(value as InspectorTab)}
              message={message}
              contextText={contextText}
              contextError={contextError}
              onMessageChange={setMessage}
              onContextChange={setContextText}
              onDispatch={submitDispatch}
              dispatchPending={dispatch.isPending}
              dispatchError={dispatch.error instanceof Error ? dispatch.error.message : null}
              gateDecision={gateDecision}
            />
          </main>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: 'info' | 'accent' | 'warn' | 'success';
}) {
  const colors = {
    info: 'text-info',
    accent: 'text-accent',
    warn: 'text-warn',
    success: 'text-success',
  };
  return (
    <div className="border-l border-border px-4 first-of-type:border-l-0 lg:first-of-type:border-l">
      <p className="text-[9px] font-semibold uppercase text-faint">{label}</p>
      <p className={cn('mt-1 font-mono text-lg font-semibold tabular-nums', colors[tone])}>{value}</p>
    </div>
  );
}

interface InspectorProps {
  graph: OrchestrationGraph;
  selectedTask: MissionTask | null;
  tab: InspectorTab;
  onTabChange: (value: string) => void;
  message: string;
  contextText: string;
  contextError: string | null;
  onMessageChange: (value: string) => void;
  onContextChange: (value: string) => void;
  onDispatch: () => void;
  dispatchPending: boolean;
  dispatchError: string | null;
  gateDecision: ReturnType<typeof useMutation<
    MissionTask,
    Error,
    { gate: ApprovalGate; decision: 'approve' | 'reject' }
  >>;
}

function Inspector({
  graph,
  selectedTask,
  tab,
  onTabChange,
  message,
  contextText,
  contextError,
  onMessageChange,
  onContextChange,
  onDispatch,
  dispatchPending,
  dispatchError,
  gateDecision,
}: InspectorProps) {
  const taskNames = new Map(graph.tasks.map((task) => [task.id, task.title]));
  return (
    <aside
      className="min-w-0 bg-surface xl:sticky xl:top-16 xl:max-h-[calc(100vh-4rem)] xl:min-h-[44rem] xl:self-start xl:overflow-y-auto"
      aria-label="Mission inspector"
    >
      <Tabs value={tab} onValueChange={onTabChange}>
        <TabsList className="grid grid-cols-4 overflow-x-auto px-2 pt-2">
          <InspectorTab value="task" icon={Sparkles} label="Task" />
          <InspectorTab value="gates" icon={ShieldCheck} label="Gates" count={graph.gates.length} />
          <InspectorTab
            value="artifacts"
            icon={FileCheck2}
            label="Files"
            count={graph.artifacts.length}
          />
          <InspectorTab value="events" icon={Activity} label="Events" count={graph.events.length} />
        </TabsList>

        <TabsContent value="task" className="inspector-panel-enter p-4">
          {!selectedTask && (
            <div className="grid min-h-72 place-items-center px-5 text-center">
              <div>
                <Sparkles className="mx-auto h-5 w-5 text-faint" />
                <p className="mt-3 text-xs font-semibold text-text">Select an Agent task</p>
                <p className="mt-1 text-[11px] leading-5 text-muted">
                  Inspect its contract, edit the instruction and dispatch it from here.
                </p>
              </div>
            </div>
          )}
          {selectedTask && (
            <div>
              <div className="flex items-start justify-between gap-3 border-b border-border pb-4">
                <div className="min-w-0">
                  <p className="text-sm font-semibold leading-5 text-text">{selectedTask.title}</p>
                  <p className="mt-1 truncate font-mono text-[9px] text-faint">
                    {selectedTask.idempotency_key}
                  </p>
                </div>
                <Badge size="sm" variant={TASK_STATUS[selectedTask.status].variant}>
                  {TASK_STATUS[selectedTask.status].label}
                </Badge>
              </div>

              <dl className="grid grid-cols-2 gap-x-3 gap-y-3 border-b border-border py-4 text-[10px]">
                <Detail label="Agent" value={selectedTask.agent_type ?? 'Unassigned'} />
                <Detail label="Role" value={selectedTask.role} />
                <Detail label="Priority" value={String(selectedTask.priority)} />
                <Detail label="Attempt" value={`${selectedTask.attempt}/${selectedTask.max_attempts}`} />
              </dl>

              {selectedTask.acceptance_json.length > 0 && (
                <section className="border-b border-border py-4">
                  <h3 className="text-[10px] font-semibold uppercase text-faint">Acceptance</h3>
                  <ul className="mt-2 space-y-2">
                    {selectedTask.acceptance_json.map((criterion) => (
                      <li key={criterion} className="flex gap-2 text-[11px] leading-4 text-muted">
                        <Check className="mt-0.5 h-3 w-3 shrink-0 text-success" /> {criterion}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <label className="mt-4 block">
                <span className="mb-1.5 block text-[10px] font-semibold uppercase text-faint">
                  Instruction
                </span>
                <Textarea
                  value={message}
                  onChange={(event) => onMessageChange(event.target.value)}
                  rows={5}
                  className="resize-y text-[11px] leading-5"
                  aria-label="Agent task instruction"
                />
              </label>
              <label className="mt-3 block">
                <span className="mb-1.5 block text-[10px] font-semibold uppercase text-faint">
                  Context JSON
                </span>
                <Textarea
                  value={contextText}
                  onChange={(event) => onContextChange(event.target.value)}
                  rows={6}
                  className="resize-y font-mono text-[10px] leading-4"
                  aria-invalid={Boolean(contextError)}
                  aria-label="Agent context JSON"
                />
              </label>
              {contextError && <p className="mt-1 text-[10px] text-danger">{contextError}</p>}
              <Button
                className="mt-3 w-full"
                size="sm"
                loading={dispatchPending}
                disabled={
                  selectedTask.status !== 'ready' || !selectedTask.agent_type || !message.trim()
                }
                onClick={onDispatch}
              >
                <Play className="h-3.5 w-3.5" /> Dispatch agent
              </Button>
              {dispatchError && <p className="mt-2 text-[10px] text-danger">{dispatchError}</p>}
            </div>
          )}
        </TabsContent>

        <TabsContent value="gates" className="inspector-panel-enter space-y-2 p-3">
          {graph.gates.map((gate) => {
            const task = graph.tasks.find((item) => item.id === gate.task_id);
            const actionable = gate.status === 'pending' && task?.status === 'waiting_approval';
            return (
              <article key={gate.id} className="rounded-md border border-border bg-bg p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-text">{gate.gate_kind}</p>
                    <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">{task?.title}</p>
                  </div>
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
                {actionable && (
                  <div className="mt-3 grid grid-cols-2 gap-2 border-t border-border pt-3">
                    <Button
                      size="sm"
                      loading={gateDecision.isPending && gateDecision.variables?.gate.id === gate.id}
                      onClick={() => gateDecision.mutate({ gate, decision: 'approve' })}
                    >
                      <Check className="h-3.5 w-3.5" /> Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-danger"
                      onClick={() => gateDecision.mutate({ gate, decision: 'reject' })}
                    >
                      <X className="h-3.5 w-3.5" /> Reject
                    </Button>
                  </div>
                )}
              </article>
            );
          })}
          {graph.gates.length === 0 && <InspectorEmpty label="No approval gates" />}
          {gateDecision.error instanceof Error && (
            <p className="text-[10px] text-danger">{gateDecision.error.message}</p>
          )}
        </TabsContent>

        <TabsContent value="artifacts" className="inspector-panel-enter space-y-2 p-3">
          {graph.artifacts.map((artifact) => (
            <article key={artifact.id} className="rounded-md border border-border bg-bg p-3">
              <div className="flex items-start gap-2">
                <FileCheck2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-text">
                    {artifact.schema_name}/v{artifact.schema_version}
                  </p>
                  <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">
                    {taskNames.get(artifact.task_id) ?? 'Unknown producer'}
                  </p>
                  <p className="mt-2 break-all font-mono text-[9px] leading-4 text-faint">
                    sha256:{artifact.content_hash}
                  </p>
                </div>
              </div>
            </article>
          ))}
          {graph.artifacts.length === 0 && <InspectorEmpty label="No artifacts yet" />}
        </TabsContent>

        <TabsContent value="events" className="inspector-panel-enter p-4">
          <ol className="relative space-y-0 before:absolute before:bottom-3 before:left-[5px] before:top-3 before:w-px before:bg-border-strong">
            {graph.events.map((event) => (
              <li key={event.id} className="relative grid grid-cols-[0.75rem_minmax(0,1fr)] gap-3 pb-5 last:pb-0">
                <span className="relative z-10 mt-1 h-2.5 w-2.5 rounded-full border-2 border-surface bg-accent" />
                <div className="min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="truncate text-[11px] font-semibold text-text">{event.event_type}</p>
                    <time className="shrink-0 font-mono text-[9px] text-faint">
                      {new Date(event.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </time>
                  </div>
                  <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">
                    {event.message || taskNames.get(event.task_id) || `event #${event.seq}`}
                  </p>
                </div>
              </li>
            ))}
          </ol>
          {graph.events.length === 0 && <InspectorEmpty label="No task events" />}
        </TabsContent>
      </Tabs>
    </aside>
  );
}

function InspectorTab({
  value,
  icon: Icon,
  label,
  count,
}: {
  value: InspectorTab;
  icon: typeof Clock3;
  label: string;
  count?: number;
}) {
  return (
    <TabsTrigger value={value} className="min-w-0 px-1.5 text-[10px] sm:px-2">
      <span className="inline-flex min-w-0 items-center gap-1">
        <Icon className="h-3 w-3 shrink-0" />
        <span className="truncate">{label}</span>
        {count !== undefined && <span className="font-mono text-faint">{count}</span>}
      </span>
    </TabsTrigger>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-faint">{label}</dt>
      <dd className="mt-0.5 truncate font-medium text-text">{value}</dd>
    </div>
  );
}

function InspectorEmpty({ label }: { label: string }) {
  return (
    <div className="grid min-h-48 place-items-center text-center text-[11px] text-faint">{label}</div>
  );
}
