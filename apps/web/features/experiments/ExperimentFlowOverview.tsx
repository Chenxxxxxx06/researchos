'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Code2,
  FileText,
  FlaskConical,
  Lightbulb,
  Loader2,
  GraduationCap,
  RefreshCw,
  Trophy,
} from 'lucide-react';
import { useState } from 'react';
import Link from 'next/link';

import { createAgentRun, getAgentRun } from '@/lib/api/agents';
import {
  listExperiments,
  listLogs,
  listMetrics,
  listProjectRuns,
  type ExperimentRun,
} from '@/lib/api/experiments';
import { listIdeas } from '@/lib/api/ideas';
import { listPapers } from '@/lib/api/papers';
import { listLLMConfigs } from '@/lib/api/llmConfig';
import { installSkill } from '@/lib/api/skills';
import { EvidenceStamp } from '@/components/provenance/EvidenceStamp';
import { ProvenanceTrace } from '@/components/provenance/ProvenanceTrace';
import { cn } from '@/lib/utils';

const nodeClass =
  'min-w-[8rem] rounded-xl border border-border bg-surface px-3 py-3';

export function ExperimentFlowOverview({ projectId }: { projectId: string }) {
  const papers = useQuery({
    queryKey: ['papers', projectId],
    queryFn: () => listPapers(projectId, { limit: 1 }),
  });
  const ideas = useQuery({
    queryKey: ['ideas', projectId],
    queryFn: () => listIdeas(projectId, { limit: 1 }),
  });
  const experiments = useQuery({
    queryKey: ['experiments', projectId],
    queryFn: () => listExperiments(projectId),
  });
  const runs = useQuery({
    queryKey: ['project-runs', projectId],
    queryFn: () => listProjectRuns(projectId),
    refetchInterval: (query) =>
      query.state.data?.some((run) => run.status === 'running' || run.status === 'queued')
        ? 3000
        : false,
  });

  const allRuns = runs.data ?? [];
  const completed = allRuns.filter((run) => run.status === 'completed').length;
  const stages = [
    { label: '文献证据', detail: `${papers.data?.total ?? 0} 篇`, icon: BookOpen, ready: (papers.data?.total ?? 0) > 0 },
    { label: '研究假设', detail: `${ideas.data?.total ?? 0} 个`, icon: Lightbulb, ready: (ideas.data?.total ?? 0) > 0 },
    { label: '代码版本', detail: `${allRuns.filter((r) => r.git_commit).length} 个提交`, icon: Code2, ready: allRuns.some((r) => r.git_commit) },
    { label: '实验运行', detail: `${allRuns.length} 次`, icon: FlaskConical, ready: allRuns.length > 0 },
    { label: '结果比较', detail: `${completed} 次完成`, icon: BarChart3, ready: completed >= 2 },
    { label: '最优方案', detail: completed ? '等待指标判定' : '尚无结果', icon: Trophy, ready: completed > 0 },
    { label: '论文汇总', detail: '图表与结论', icon: FileText, ready: false },
  ];

  return (
    <div className="space-y-6">
      <section>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-text">科研数据链路</h2>
            <p className="mt-1 text-sm text-muted">
              每一步都保留来源和版本关系，使论文结论可以回溯到文献、代码、运行指标和图表。
            </p>
          </div>
          <ProvenanceTrace
            nodes={[
              { label: '文献', state: (papers.data?.total ?? 0) > 0 ? 'done' : 'todo' },
              { label: '假设', state: (ideas.data?.total ?? 0) > 0 ? 'done' : 'todo' },
              { label: '实验', state: allRuns.length > 0 ? 'done' : 'todo' },
              { label: '论文', state: 'todo' },
            ]}
          />
        </div>
        <div className="mt-4 flex items-stretch gap-2 overflow-x-auto pb-2">
          {stages.map((stage, index) => {
            const Icon = stage.icon;
            return (
              <div key={stage.label} className="flex items-center gap-2">
                <div className={cn(nodeClass, stage.ready && 'border-success/40 bg-success-bg/30')}>
                  <Icon className={cn('mb-2 h-4 w-4', stage.ready ? 'text-success' : 'text-muted')} />
                  <p className="text-xs font-semibold text-text">{stage.label}</p>
                  <p className="mt-1 text-[11px] text-muted">{stage.detail}</p>
                </div>
                {index < stages.length - 1 && <ArrowRight className="h-4 w-4 shrink-0 text-faint" />}
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="text-base font-semibold text-text">全部运行进度</h2>
            <p className="mt-1 text-xs text-muted">
              Runner 可通过状态上报协议写入 progress 和 current_step。
            </p>
          </div>
          <span className="text-xs text-muted">{experiments.data?.length ?? 0} 个实验</span>
        </div>
        {allRuns.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border-strong p-8 text-center text-sm text-muted">
            创建实验并由本地或远程 Runner 启动后，进度会显示在这里。
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {allRuns.map((run) => <RunProgress key={run.id} run={run} />)}
          </div>
        )}
      </section>

      <MentorPanel
        projectId={projectId}
        runs={allRuns}
        experimentCount={experiments.data?.length ?? 0}
        paperCount={papers.data?.total ?? 0}
        ideaCount={ideas.data?.total ?? 0}
      />
    </div>
  );
}

function MentorPanel({ projectId, runs, experimentCount, paperCount, ideaCount }: { projectId: string; runs: ExperimentRun[]; experimentCount: number; paperCount: number; ideaCount: number }) {
  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [runId, setRunId] = useState<string | null>(null);
  const configs = useQuery({ queryKey: ['llm-configs', projectId], queryFn: () => listLLMConfigs(projectId) });
  const realProviderReady = Boolean(configs.data?.some((item) => item.is_active));
  const effectiveRunId = selectedRunId || runs[0]?.id || '';
  const selectedRun = runs.find((item) => item.id === effectiveRunId) ?? null;
  const metrics = useQuery({
    queryKey: ['mentor-metrics', projectId, effectiveRunId],
    queryFn: () => listMetrics(projectId, effectiveRunId),
    enabled: Boolean(effectiveRunId),
  });
  const logs = useQuery({
    queryKey: ['mentor-logs', projectId, effectiveRunId],
    queryFn: () => listLogs(projectId, effectiveRunId),
    enabled: Boolean(effectiveRunId),
  });
  const start = useMutation({
    mutationFn: async () => {
      await installSkill(projectId, 'research-mentor');
      return createAgentRun(projectId, {
        agent_type: 'research',
        context: { skill_slugs: ['research-mentor'] },
        message: mentorPrompt({
          paperCount,
          ideaCount,
          experimentCount,
          runs,
          selectedRun,
          metrics: metrics.data ?? [],
          logs: logs.data ?? [],
        }),
      });
    },
    onSuccess: (result) => setRunId(result.agent_run_id),
  });
  const agentRun = useQuery({
    queryKey: ['mentor-run', projectId, runId],
    queryFn: () => getAgentRun(projectId, runId!),
    enabled: Boolean(runId),
    refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1500 : false,
  });

  return (
    <section className="overflow-hidden border border-accent/25 bg-accent/5">
      <div className="grid lg:grid-cols-[20rem_minmax(0,1fr)]">
        <div className="border-b border-accent/15 p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-2"><GraduationCap className="h-4 w-4 text-accent" /><h3 className="text-sm font-semibold text-text">实验导师 Skill</h3></div>
          <p className="mt-2 text-xs leading-5 text-muted">读取当前项目与选中运行的真实指标、日志和版本信息，给出可证伪、按信息增益排序的下一步建议。</p>
          <label className="mt-4 block text-[10px] font-semibold uppercase tracking-wider text-faint">重点运行</label>
          <select value={effectiveRunId} onChange={(event) => setSelectedRunId(event.target.value)} className="mt-1 h-10 w-full border border-border-strong bg-surface px-3 text-xs text-text">
            {runs.length === 0 && <option value="">尚无实验运行</option>}
            {runs.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.status}</option>)}
          </select>
          <button type="button" disabled={!realProviderReady || start.isPending || metrics.isLoading || logs.isLoading} onClick={() => start.mutate()} className="mt-3 inline-flex h-10 w-full items-center justify-center gap-2 bg-accent px-4 text-xs font-semibold text-accent-fg disabled:cursor-not-allowed disabled:opacity-50">
            {start.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {runId ? '重新生成导师建议' : '生成导师建议'}
          </button>
          <p className="mt-3 font-mono text-[9px] leading-4 text-faint">SKILL research-mentor · evidence-bound · no fabricated metrics</p>
          {!realProviderReady && !configs.isLoading && <p className="mt-3 border border-warn/25 bg-warn-bg p-2 text-[10px] leading-4 text-warn">导师 Agent 已锁定，请先在<Link href={`/projects/${projectId}/manage?tab=settings`} className="mx-1 font-semibold underline">管理中心</Link>配置真实模型。</p>}
        </div>
        <div className="min-h-[16rem] bg-surface/70 p-5">
          {!runId && <div className="flex h-full min-h-[12rem] items-center justify-center text-center text-xs leading-6 text-muted">选择一个运行后，导师会检查主张—证据链、混杂因素、对照、消融、复现信息和停止条件。</div>}
          {agentRun.data && ['queued', 'running'].includes(agentRun.data.status) && <div className="flex items-center gap-2 text-sm text-info"><Loader2 className="h-4 w-4 animate-spin" />导师 Agent 正在检查实验记录…</div>}
          {agentRun.data?.status === 'failed' && <div className="border border-danger/20 bg-danger-bg p-3 text-xs text-danger">{agentRun.data.error_json?.message || '生成失败，请在管理中心检查模型连接与 Worker。'}</div>}
          {agentRun.data?.status === 'completed' && <article className="whitespace-pre-wrap text-sm leading-7 text-text">{typeof agentRun.data.output_json?.message === 'string' ? agentRun.data.output_json.message : '运行完成，但没有返回可显示的导师报告。'}</article>}
          {start.error && <div className="border border-danger/20 bg-danger-bg p-3 text-xs text-danger">{start.error instanceof Error ? start.error.message : '无法启动导师 Agent。'}</div>}
        </div>
      </div>
    </section>
  );
}

function mentorPrompt(input: { paperCount: number; ideaCount: number; experimentCount: number; runs: ExperimentRun[]; selectedRun: ExperimentRun | null; metrics: Array<{ name: string; step: number; value: number }>; logs: Array<{ seq: number; level: string; message: string }> }): string {
  const record = {
    project_state: { papers: input.paperCount, ideas: input.ideaCount, experiments: input.experimentCount, runs: input.runs.length },
    run_portfolio: input.runs.slice(0, 20).map((run) => ({ id: run.id, name: run.name, status: run.status, git_commit: run.git_commit, command: run.command, progress: run.progress, config: run.config_json })),
    selected_run: input.selectedRun,
    recorded_metrics: input.metrics.slice(-200),
    recent_logs: input.logs.slice(-40),
  };
  return `Use the active Research Mentor skill to conduct a project checkpoint. Treat the JSON below as the complete available experiment record. Do not infer that a metric improved unless the recorded values prove it. Return in Chinese: (1) current stage and evidence inventory; (2) claim-to-evidence audit; (3) fatal gaps and confounds; (4) smallest decisive next experiment with hypothesis, independent/dependent/control variables, baseline, primary metric, success/failure thresholds and stop rule; (5) ordered checklist for this week; (6) what must be logged for reproducibility. Mark absent data as [证据缺口].\n\nPROJECT RECORD:\n${JSON.stringify(record).slice(0, 8500)}`;
}

function RunProgress({ run }: { run: ExperimentRun }) {
  const currentStep =
    typeof run.config_json.current_step === 'string' ? run.config_json.current_step : null;
  const progress = Math.max(0, Math.min(100, run.progress ?? 0));
  return (
    <article className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-text">{run.name}</p>
          <p className="mt-0.5 truncate text-[11px] text-muted">
            {currentStep ?? run.status}
          </p>
        </div>
        <span className="font-mono text-xs text-muted">{progress.toFixed(0)}%</span>
      </div>
      <div className="mt-3">
        <EvidenceStamp
          status={run.status}
          tone={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'danger' : run.status === 'running' ? 'accent' : 'neutral'}
          id={run.id.slice(0, 8)}
          date={new Date(run.created_at).toLocaleDateString()}
        />
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-3">
        <div
          className={cn(
            'h-full rounded-full transition-[width] duration-500',
            run.status === 'failed' ? 'bg-danger' : run.status === 'completed' ? 'bg-success' : 'bg-accent',
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </article>
  );
}
