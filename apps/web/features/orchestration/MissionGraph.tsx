import {
  AlertTriangle,
  ArrowRight,
  Bot,
  Check,
  Circle,
  Clock3,
  Code2,
  FileText,
  FlaskConical,
  Search,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';

import { Badge, type BadgeProps } from '@/components/ui/badge';
import type {
  MissionTask,
  MissionTaskStatus,
  TaskArtifact,
} from '@/lib/api/orchestration';
import { cn } from '@/lib/utils';

interface Lane {
  index: string;
  title: string;
  description: string;
  keys: string[];
  icon: LucideIcon;
}

const LANES: Lane[] = [
  {
    index: '01',
    title: 'Evidence & direction',
    description: 'Find, read, challenge, decide',
    keys: ['scope', 'discover', 'read', 'synthesize', 'idea_rank', 'benchmark', 'critic', 'direction'],
    icon: Search,
  },
  {
    index: '02',
    title: 'Repository & build',
    description: 'Pin source, reproduce, propose',
    keys: ['repository', 'baseline', 'coding', 'code_check', 'pilot', 'pilot_review', 'leader', 'experiment_plan'],
    icon: Code2,
  },
  {
    index: '03',
    title: 'Experiment & analysis',
    description: 'Run bounded loops, verify evidence',
    keys: ['experiment_run', 'progress', 'reproduce', 'analyze'],
    icon: FlaskConical,
  },
  {
    index: '04',
    title: 'Write & release',
    description: 'Bind claims, review, authorize',
    keys: ['writer_outline', 'writer_results', 'drawer', 'citation', 'review', 'release'],
    icon: FileText,
  },
];

export const TASK_STATUS: Record<
  MissionTaskStatus,
  { label: string; variant: BadgeProps['variant'] }
> = {
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

interface Props {
  tasks: MissionTask[];
  dependencies: Map<string, string[]>;
  artifacts: TaskArtifact[];
  selectedTaskId: string | null;
  onSelect: (task: MissionTask) => void;
}

export function MissionGraph({
  tasks,
  dependencies,
  artifacts,
  selectedTaskId,
  onSelect,
}: Props) {
  return (
    <div className="min-w-0 bg-bg">
      <nav
        aria-label="Research phases"
        className="sticky top-0 z-20 overflow-x-auto border-b border-border bg-overlay/95 px-3 py-2 backdrop-blur md:hidden"
      >
        <ol className="grid min-w-[31rem] grid-cols-4 gap-1">
          {LANES.map((lane) => {
            const laneTasks = lane.keys
              .map((key) => tasks.find((task) => task.task_key === key))
              .filter((task): task is MissionTask => Boolean(task));
            const done = laneTasks.filter((task) => task.status === 'completed').length;
            return (
              <li key={lane.index}>
                <a
                  href={`#mission-phase-${lane.index}`}
                  className="flex h-9 items-center gap-2 rounded-md px-2 text-[10px] text-muted hover:bg-surface-2 hover:text-text"
                >
                  <span className="font-mono text-accent">{lane.index}</span>
                  <span className="truncate">{lane.title.split(' & ')[0]}</span>
                  <span className="ml-auto font-mono text-faint">
                    {done}/{laneTasks.length}
                  </span>
                </a>
              </li>
            );
          })}
        </ol>
      </nav>
      {LANES.map((lane) => {
        const laneTasks = lane.keys
          .map((key) => tasks.find((task) => task.task_key === key))
          .filter((task): task is MissionTask => Boolean(task));
        const completed = laneTasks.filter((task) => task.status === 'completed').length;
        const progress = laneTasks.length ? Math.round((completed / laneTasks.length) * 100) : 0;
        const LaneIcon = lane.icon;
        return (
          <section
            key={lane.title}
            id={`mission-phase-${lane.index}`}
            className="scroll-mt-12 grid border-b border-border last:border-b-0 lg:grid-cols-[12rem_minmax(0,1fr)]"
          >
            <header className="mission-phase-header relative border-b border-border bg-surface px-5 py-5 lg:border-b-0 lg:border-r">
              <div className="flex items-start justify-between gap-3 lg:block">
                <div>
                  <span className="font-mono text-[10px] text-faint">PHASE {lane.index}</span>
                  <h2 className="mt-2 flex items-center gap-2 text-sm font-semibold text-text">
                    <LaneIcon className="h-4 w-4 text-accent" /> {lane.title}
                  </h2>
                  <p className="mt-1 max-w-40 text-[11px] leading-4 text-muted">
                    {lane.description}
                  </p>
                </div>
                <div className="mt-5 min-w-24 lg:w-full">
                  <div className="flex items-center justify-between font-mono text-[10px] text-faint">
                    <span>{completed}/{laneTasks.length}</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="mt-1.5 h-1 overflow-hidden rounded-sm bg-surface-2">
                    <div
                      className="h-full bg-success transition-[width] duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              </div>
            </header>

            <div className="overflow-x-auto px-5 py-5">
              <ol
                className="relative grid min-w-max grid-flow-col auto-cols-[11.5rem] gap-3"
                aria-label={`${lane.title} tasks`}
              >
                <div
                  aria-hidden="true"
                  className={cn(
                    'agent-flow-line absolute left-8 right-8 top-[2.15rem] h-px bg-border-strong',
                    laneTasks.some((task) => task.status === 'running' || task.status === 'leased') &&
                      'is-live',
                  )}
                />
                {laneTasks.map((task, index) => (
                  <li key={task.id} className="relative z-10">
                    <TaskNode
                      task={task}
                      dependencyKeys={dependencies.get(task.id) ?? []}
                      artifactCount={artifacts.filter((item) => item.task_id === task.id).length}
                      selected={selectedTaskId === task.id}
                      index={index}
                      onClick={() => onSelect(task)}
                    />
                    {index < laneTasks.length - 1 && (
                      <ArrowRight
                        aria-hidden="true"
                        className="absolute -right-2 top-[1.82rem] h-3.5 w-3.5 text-border-strong"
                      />
                    )}
                  </li>
                ))}
              </ol>
            </div>
          </section>
        );
      })}
    </div>
  );
}

function TaskNode({
  task,
  dependencyKeys,
  artifactCount,
  selected,
  index,
  onClick,
}: {
  task: MissionTask;
  dependencyKeys: string[];
  artifactCount: number;
  selected: boolean;
  index: number;
  onClick: () => void;
}) {
  const Icon = taskIcon(task.status);
  const status = TASK_STATUS[task.status];
  const live = task.status === 'running' || task.status === 'leased';
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      data-status={task.status}
      style={{ animationDelay: `${index * 45}ms` }}
      className={cn(
        'agent-node-enter group relative flex h-[8.5rem] w-full flex-col overflow-hidden rounded-md border bg-surface p-3 text-left shadow-elev1',
        'transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-elev2',
        selected && 'border-accent shadow-elev2 ring-1 ring-accent/20',
        live && 'border-success/50',
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'absolute inset-y-0 left-0 w-0.5 bg-border-strong',
          task.status === 'completed' && 'bg-success',
          task.status === 'waiting_approval' && 'bg-warn',
          task.status === 'terminal_failed' && 'bg-danger',
          live && 'bg-accent',
        )}
      />
      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            'grid h-8 w-8 place-items-center rounded-md border border-border bg-bg text-muted',
            task.status === 'completed' && 'border-success/25 bg-success-bg text-success',
            live && 'border-accent/30 bg-success-bg text-accent',
          )}
        >
          <Icon className={cn('h-4 w-4', live && 'animate-pulse')} />
        </span>
        <Badge size="sm" variant={status.variant} dot={live}>
          {status.label}
        </Badge>
      </div>
      <p className="mt-2 line-clamp-2 text-xs font-semibold leading-4 text-text">
        {task.title}
      </p>
      <div className="mt-auto flex items-center justify-between gap-2 font-mono text-[9px] text-faint">
        <span className="truncate">{task.role}</span>
        <span className="shrink-0 tabular-nums">
          {artifactCount}A · {task.attempt}/{task.max_attempts}
        </span>
      </div>
      {dependencyKeys.length > 0 && (
        <span className="sr-only">Depends on {dependencyKeys.join(', ')}</span>
      )}
    </button>
  );
}

function taskIcon(status: MissionTaskStatus): LucideIcon {
  if (status === 'completed') return Check;
  if (status === 'terminal_failed') return AlertTriangle;
  if (status === 'waiting_approval') return ShieldCheck;
  if (status === 'running' || status === 'leased') return Bot;
  if (status === 'ready') return Circle;
  return Clock3;
}
