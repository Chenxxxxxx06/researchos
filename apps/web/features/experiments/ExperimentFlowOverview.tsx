'use client';

import { useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Code2,
  FileText,
  FlaskConical,
  Lightbulb,
  Trophy,
} from 'lucide-react';

import { listExperiments, listProjectRuns, type ExperimentRun } from '@/lib/api/experiments';
import { listIdeas } from '@/lib/api/ideas';
import { listPapers } from '@/lib/api/papers';
import { cn } from '@/lib/utils';

const nodeClass =
  'min-w-[8rem] rounded-xl border border-border bg-surface px-3 py-3 shadow-elev1';

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
        <h2 className="text-lg font-semibold text-text">科研数据链路</h2>
        <p className="mt-1 text-sm text-muted">
          每一步都保留来源和版本关系，使论文结论可以回溯到文献、代码、运行指标和图表。
        </p>
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

      <section className="rounded-xl border border-accent/25 bg-accent/5 p-4">
        <h3 className="text-sm font-semibold text-text">实验规划助手</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          规划顺序固定为：主结果可支持主张后，再生成组件消融、超参数敏感性和替代设计；优先运行配置型消融，并为每个实验记录
          “它验证什么”和“组件有效时预期发生什么”。Baseline 与 benchmark 必须来自项目文献库或明确标注为待验证建议。
        </p>
      </section>
    </div>
  );
}

function RunProgress({ run }: { run: ExperimentRun }) {
  const currentStep =
    typeof run.config_json.current_step === 'string' ? run.config_json.current_step : null;
  const progress = Math.max(0, Math.min(100, run.progress ?? 0));
  return (
    <article className="rounded-xl border border-border bg-surface p-4 shadow-elev1">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-text">{run.name}</p>
          <p className="mt-0.5 truncate text-[11px] text-muted">
            {currentStep ?? run.status}
          </p>
        </div>
        <span className="font-mono text-xs text-muted">{progress.toFixed(0)}%</span>
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
