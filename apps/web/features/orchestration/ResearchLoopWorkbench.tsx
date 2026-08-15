'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  FlaskConical,
  GitCommitHorizontal,
  Pause,
  Play,
  RotateCcw,
  Square,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { listProjectRuns } from '@/lib/api/experiments';
import {
  controlResearchLoop,
  createResearchIteration,
  createResearchLoop,
  evaluateResearchIteration,
  listResearchLoops,
  type ResearchLoop,
  type ResearchLoopIteration,
} from '@/lib/api/orchestration';

interface Props {
  projectId: string;
  missionId: string;
  experimentTaskReady: boolean;
}

export function ResearchLoopWorkbench({ projectId, missionId, experimentTaskReady }: Props) {
  const queryClient = useQueryClient();
  const [baselineRunId, setBaselineRunId] = useState('');
  const [metricName, setMetricName] = useState('val_loss');
  const [direction, setDirection] = useState<'min' | 'max'>('min');
  const [hypothesis, setHypothesis] = useState('');
  const [component, setComponent] = useState('');
  const [expectedEffect, setExpectedEffect] = useState('');
  const [changedPaths, setChangedPaths] = useState('');
  const [candidateRunId, setCandidateRunId] = useState('');
  const [patchId, setPatchId] = useState('');
  const [complexityDelta, setComplexityDelta] = useState('0');
  const [criticScore, setCriticScore] = useState('0.8');

  const queryKey = ['research-loops', projectId, missionId];
  const loops = useQuery({
    queryKey,
    queryFn: () => listResearchLoops(projectId, missionId),
  });
  const runs = useQuery({
    queryKey: ['project-runs', projectId, 'research-loop'],
    queryFn: () => listProjectRuns(projectId),
  });
  const completedRuns = useMemo(
    () => (runs.data ?? []).filter((run) => run.status === 'completed' && run.git_commit),
    [runs.data],
  );
  useEffect(() => {
    if (!baselineRunId && completedRuns[0]) setBaselineRunId(completedRuns[0].id);
  }, [baselineRunId, completedRuns]);
  useEffect(() => {
    setBaselineRunId('');
  }, [missionId]);

  const current =
    loops.data?.find((loop) => loop.status === 'active' || loop.status === 'paused') ??
    loops.data?.[0] ??
    null;
  const openIteration = current?.iterations.find(
    (iteration) => iteration.status === 'proposed' || iteration.status === 'running',
  );

  const updateLoop = (loop: ResearchLoop) => {
    queryClient.setQueryData<ResearchLoop[]>(queryKey, (existing = []) => [
      loop,
      ...existing.filter((item) => item.id !== loop.id),
    ]);
  };
  const createLoopMutation = useMutation({
    mutationFn: () =>
      createResearchLoop(projectId, missionId, {
        name: `${metricName} optimization`,
        metric_name: metricName.trim(),
        metric_direction: direction,
        metric_aggregation: 'final',
        baseline_run_id: baselineRunId,
        fixed_budget_seconds: 300,
        max_iterations: 12,
        patience: 4,
        min_delta: 0.001,
        max_complexity_delta: 200,
        critic_threshold: 0.7,
        editable_scopes: ['src'],
        protected_scopes: ['src/eval.py', 'prepare.py'],
      }),
    onSuccess: updateLoop,
  });
  const proposeMutation = useMutation({
    mutationFn: () =>
      createResearchIteration(projectId, current?.id ?? '', {
        hypothesis: hypothesis.trim(),
        component: component.trim(),
        expected_effect: expectedEffect.trim(),
        changed_paths: changedPaths
          .split('\n')
          .map((path) => path.trim())
          .filter(Boolean),
      }),
    onSuccess: (loop) => {
      updateLoop(loop);
      setHypothesis('');
      setComponent('');
      setExpectedEffect('');
      setChangedPaths('');
    },
  });
  const evaluateMutation = useMutation({
    mutationFn: () =>
      evaluateResearchIteration(projectId, openIteration?.id ?? '', {
        experiment_run_id: candidateRunId,
        ...(patchId.trim() ? { patch_id: patchId.trim() } : {}),
        complexity_delta: Number(complexityDelta),
        critic_score: Number(criticScore),
        rule_checks: { reproducible: true, artifact_integrity: true },
      }),
    onSuccess: (loop) => {
      updateLoop(loop);
      setCandidateRunId('');
      setPatchId('');
      setComplexityDelta('0');
    },
  });
  const controlMutation = useMutation({
    mutationFn: (action: 'pause' | 'resume' | 'finalize') =>
      controlResearchLoop(projectId, current?.id ?? '', action),
    onSuccess: updateLoop,
  });
  const error =
    createLoopMutation.error ??
    proposeMutation.error ??
    evaluateMutation.error ??
    controlMutation.error;

  if (loops.isLoading || runs.isLoading) {
    return <div className="h-32 animate-pulse border-b border-border bg-surface-2" />;
  }

  return (
    <section className="border-b border-border bg-surface" aria-labelledby="research-loop-title">
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-accent text-accent-fg">
            <RotateCcw className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <h2 id="research-loop-title" className="text-sm font-semibold text-text">
              Research loop
            </h2>
            <p className="truncate text-[11px] text-muted">
              rollout · evaluate · update · accept
            </p>
          </div>
        </div>
        {current && <LoopSummary loop={current} />}
      </header>

      {!current && (
        <form
          className="grid gap-3 border-t border-border px-5 py-4 md:grid-cols-[minmax(12rem,1fr)_minmax(10rem,0.7fr)_8rem_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            createLoopMutation.mutate();
          }}
        >
          <Field label="Baseline run">
            <select
              value={baselineRunId}
              onChange={(event) => setBaselineRunId(event.target.value)}
              className="h-9 w-full rounded-md border border-border-strong bg-bg px-3 text-xs text-text"
              required
            >
              <option value="">Select completed run</option>
              {completedRuns.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.name} · {run.git_commit?.slice(0, 8)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Primary metric">
            <Input
              value={metricName}
              onChange={(event) => setMetricName(event.target.value)}
              className="h-9 text-xs"
              required
            />
          </Field>
          <Field label="Direction">
            <select
              value={direction}
              onChange={(event) => setDirection(event.target.value as 'min' | 'max')}
              className="h-9 w-full rounded-md border border-border-strong bg-bg px-3 text-xs text-text"
            >
              <option value="min">Minimize</option>
              <option value="max">Maximize</option>
            </select>
          </Field>
          <Button
            type="submit"
            size="sm"
            className="self-end"
            loading={createLoopMutation.isPending}
            disabled={!experimentTaskReady || !baselineRunId || !metricName.trim()}
          >
            <Play className="h-3.5 w-3.5" /> Start loop
          </Button>
        </form>
      )}

      {current && (
        <div className="grid border-t border-border xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="min-w-0 border-b border-border xl:border-b-0 xl:border-r">
            <IterationLedger loop={current} />
          </div>
          <div className="p-4">
            {current.status === 'active' && !openIteration && (
              <form
                className="space-y-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  proposeMutation.mutate();
                }}
              >
                <Field label="Single component">
                  <Input
                    value={component}
                    onChange={(event) => setComponent(event.target.value)}
                    placeholder="optimizer.learning_rate"
                    className="h-9 text-xs"
                    required
                  />
                </Field>
                <Field label="Hypothesis">
                  <Textarea
                    value={hypothesis}
                    onChange={(event) => setHypothesis(event.target.value)}
                    rows={2}
                    className="text-xs"
                    required
                  />
                </Field>
                <Field label="Expected effect">
                  <Textarea
                    value={expectedEffect}
                    onChange={(event) => setExpectedEffect(event.target.value)}
                    rows={2}
                    className="text-xs"
                    required
                  />
                </Field>
                <Field label="Changed paths · one per line">
                  <Textarea
                    value={changedPaths}
                    onChange={(event) => setChangedPaths(event.target.value)}
                    rows={2}
                    className="font-mono text-xs"
                    required
                  />
                </Field>
                <Button type="submit" size="sm" loading={proposeMutation.isPending}>
                  <FlaskConical className="h-3.5 w-3.5" /> Propose iteration
                </Button>
              </form>
            )}
            {current.status === 'active' && openIteration && (
              <form
                className="space-y-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  evaluateMutation.mutate();
                }}
              >
                <p className="text-xs font-semibold text-text">
                  Evaluate iteration {openIteration.iteration_number}
                </p>
                <Field label="Candidate run">
                  <select
                    value={candidateRunId}
                    onChange={(event) => setCandidateRunId(event.target.value)}
                    className="h-9 w-full rounded-md border border-border-strong bg-bg px-3 text-xs text-text"
                    required
                  >
                    <option value="">Select completed run</option>
                    {completedRuns
                      .filter((run) => run.id !== current.baseline_run_id)
                      .map((run) => (
                        <option key={run.id} value={run.id}>
                          {run.name} · {run.git_commit?.slice(0, 8)}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field label="Applied patch ID">
                  <Input
                    value={patchId}
                    onChange={(event) => setPatchId(event.target.value)}
                    className="h-9 font-mono text-xs"
                  />
                </Field>
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Complexity Δ">
                    <Input
                      type="number"
                      value={complexityDelta}
                      onChange={(event) => setComplexityDelta(event.target.value)}
                      className="h-9 text-xs"
                    />
                  </Field>
                  <Field label="Critic score">
                    <Input
                      type="number"
                      min="0"
                      max="1"
                      step="0.05"
                      value={criticScore}
                      onChange={(event) => setCriticScore(event.target.value)}
                      className="h-9 text-xs"
                    />
                  </Field>
                </div>
                <Button
                  type="submit"
                  size="sm"
                  loading={evaluateMutation.isPending}
                  disabled={!candidateRunId}
                >
                  <CheckCircle2 className="h-3.5 w-3.5" /> Evaluate
                </Button>
              </form>
            )}
            {current.status === 'paused' && (
              <p className="text-xs text-muted">{current.stop_reason}</p>
            )}
            <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3">
              {current.status === 'active' && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => controlMutation.mutate('pause')}
                >
                  <Pause className="h-3.5 w-3.5" /> Pause
                </Button>
              )}
              {current.status === 'paused' && (
                <Button size="sm" onClick={() => controlMutation.mutate('resume')}>
                  <Play className="h-3.5 w-3.5" /> Resume
                </Button>
              )}
              {(current.status === 'active' || current.status === 'paused') && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => controlMutation.mutate('finalize')}
                >
                  <Square className="h-3.5 w-3.5" /> Finalize best
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
      {error instanceof Error && (
        <p className="border-t border-danger/20 bg-danger-bg px-5 py-2 text-xs text-danger">
          {error.message}
        </p>
      )}
    </section>
  );
}

function LoopSummary({ loop }: { loop: ResearchLoop }) {
  const improved =
    loop.metric_direction === 'min'
      ? loop.best_metric_value < loop.baseline_metric_value
      : loop.best_metric_value > loop.baseline_metric_value;
  const DirectionIcon = loop.metric_direction === 'min' ? TrendingDown : TrendingUp;
  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px]">
      <Badge
        size="sm"
        variant={
          loop.status === 'completed' ? 'success' : loop.status === 'paused' ? 'warn' : 'accent'
        }
        dot
      >
        {loop.status}
      </Badge>
      <span className="font-mono text-muted">
        {loop.metric_name} {loop.best_metric_value.toPrecision(5)}
      </span>
      <span className={improved ? 'text-success' : 'text-muted'}>
        <DirectionIcon className="mr-1 inline h-3 w-3" />
        {loop.current_iteration}/{loop.max_iterations}
      </span>
    </div>
  );
}

function IterationLedger({ loop }: { loop: ResearchLoop }) {
  if (!loop.iterations.length) {
    return (
      <div className="grid min-h-40 place-items-center px-6 py-8 text-xs text-muted">
        No candidate iterations
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[42rem] text-left text-xs">
        <thead className="border-b border-border bg-surface-2 text-[10px] font-semibold text-muted">
          <tr>
            <th className="px-4 py-2">#</th>
            <th className="px-4 py-2">Component</th>
            <th className="px-4 py-2">Commit</th>
            <th className="px-4 py-2">Metric</th>
            <th className="px-4 py-2">Δ</th>
            <th className="px-4 py-2">Decision</th>
          </tr>
        </thead>
        <tbody>
          {loop.iterations.map((iteration) => (
            <IterationRow key={iteration.id} iteration={iteration} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IterationRow({ iteration }: { iteration: ResearchLoopIteration }) {
  const variant =
    iteration.status === 'kept'
      ? 'success'
      : iteration.status === 'discarded' || iteration.status === 'crashed'
        ? 'danger'
        : 'warn';
  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-4 py-3 font-mono text-faint">{iteration.iteration_number}</td>
      <td className="max-w-64 px-4 py-3">
        <p className="truncate font-medium text-text">{iteration.component}</p>
        <p className="mt-0.5 truncate text-[10px] text-muted">{iteration.hypothesis}</p>
      </td>
      <td className="px-4 py-3 font-mono text-[10px] text-muted">
        <GitCommitHorizontal className="mr-1 inline h-3 w-3" />
        {iteration.code_commit_sha?.slice(0, 8) ?? 'pending'}
      </td>
      <td className="px-4 py-3 font-mono tabular-nums text-text">
        {iteration.metric_value?.toPrecision(5) ?? '—'}
      </td>
      <td className="px-4 py-3 font-mono tabular-nums text-muted">
        {iteration.improvement == null
          ? '—'
          : `${iteration.improvement >= 0 ? '+' : ''}${iteration.improvement.toPrecision(3)}`}
      </td>
      <td className="px-4 py-3">
        <Badge size="sm" variant={variant}>
          {iteration.status}
        </Badge>
      </td>
    </tr>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[10px] font-medium text-muted">{label}</span>
      {children}
    </label>
  );
}
