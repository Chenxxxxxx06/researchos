'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  CheckCircle2,
  FileSearch2,
  FileText,
  FlaskConical,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { useState } from 'react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { createAgentRun, getAgentRun } from '@/lib/api/agents';
import { getFile, listLatexProjects } from '@/lib/api/documents';
import { listMetrics, listProjectRuns } from '@/lib/api/experiments';
import { listIdeas } from '@/lib/api/ideas';
import { installSkill } from '@/lib/api/skills';
import { listLLMConfigs } from '@/lib/api/llmConfig';

const VENUES = ['General CS', 'NeurIPS', 'ICML', 'ICLR', 'ACL', 'CVPR', 'AAAI', 'Nature'];

export function ReviewerWorkspace({ projectId }: { projectId: string }) {
  const [venue, setVenue] = useState('General CS');
  const [manuscript, setManuscript] = useState('');
  const [includeExperiments, setIncludeExperiments] = useState(true);
  const [runId, setRunId] = useState<string | null>(null);
  const configs = useQuery({ queryKey: ['llm-configs', projectId], queryFn: () => listLLMConfigs(projectId) });
  const realProviderReady = Boolean(configs.data?.some((item) => item.is_active));
  const latexProjects = useQuery({
    queryKey: ['latex-projects', projectId],
    queryFn: () => listLatexProjects(projectId),
  });
  const activeLatexProject = latexProjects.data?.[0];
  const paperFile = useQuery({
    queryKey: ['reviewer-paper-file', projectId, activeLatexProject?.id],
    queryFn: () => getFile(projectId, activeLatexProject!.id, activeLatexProject!.main_file_path),
    enabled: Boolean(activeLatexProject),
    retry: false,
  });
  const runs = useQuery({
    queryKey: ['project-runs', projectId],
    queryFn: () => listProjectRuns(projectId),
  });
  const ideas = useQuery({
    queryKey: ['ideas', projectId, 'review-context'],
    queryFn: () => listIdeas(projectId, { limit: 20 }),
  });
  const experimentEvidence = useQuery({
    queryKey: ['review-experiment-evidence', projectId, runs.data?.map((item) => item.id).join(',')],
    queryFn: async () => {
      const candidates = (runs.data ?? []).filter((item) => item.status === 'completed').slice(0, 8);
      return Promise.all(candidates.map(async (item) => ({
        run: item,
        metrics: await listMetrics(projectId, item.id),
      })));
    },
    enabled: Boolean(runs.data),
  });
  const start = useMutation({
    mutationFn: async () => {
      await installSkill(projectId, 'reviewer-challenger');
      return createAgentRun(projectId, {
        agent_type: 'research',
        context: { skill_slugs: ['reviewer-challenger'] },
        message: reviewerPrompt({
          venue,
          manuscript,
          ideas: ideas.data?.items ?? [],
          experiments: includeExperiments ? experimentEvidence.data ?? [] : [],
        }),
      });
    },
    onSuccess: (result) => setRunId(result.agent_run_id),
  });
  const run = useQuery({
    queryKey: ['reviewer-run', projectId, runId],
    queryFn: () => getAgentRun(projectId, runId!),
    enabled: Boolean(runId),
    refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1500 : false,
  });
  const output = run.data?.output_json?.message;

  return (
    <div className="-m-6 min-h-[calc(100dvh-3.5rem)] bg-bg lg:-m-8">
      <header className="mission-grid border-b border-border bg-surface px-6 py-7 lg:px-8">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <Badge variant="neutral" size="sm">REVIEWER CHALLENGER</Badge>
            <h1 className="mt-4 flex items-center gap-3 text-3xl font-semibold tracking-[-0.04em] text-text"><ShieldCheck className="h-7 w-7 text-accent" />模拟审稿</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">把论文工作区、研究想法和已记录实验结果放到同一份证据包中检查。输出是修改决策支持，不冒充真实审稿结果。</p>
          </div>
          <div className="border border-success/20 bg-success-bg/70 px-4 py-3 text-xs text-success"><span className="font-semibold">真实性边界</span><p className="mt-1 text-[10px] opacity-80">不虚构指标、引用、结果或录用概率</p></div>
        </div>
      </header>

      <div className="grid gap-6 p-6 xl:grid-cols-[27rem_minmax(0,1fr)] lg:p-8">
        <section className="h-fit border border-border bg-surface p-5 shadow-sm">
          <div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-text">01 · 构建审稿证据包</h2><FileSearch2 className="h-4 w-4 text-accent" /></div>
          <label className="mt-5 block text-xs font-medium text-text">目标会议 / 期刊
            <select value={venue} onChange={(event) => setVenue(event.target.value)} className="mt-1 h-10 w-full border border-border-strong bg-surface px-3 text-sm">
              {VENUES.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <div className="mt-4 border border-border bg-surface-2/50 p-3">
            <div className="flex items-start justify-between gap-3">
              <div><p className="flex items-center gap-2 text-xs font-medium text-text"><FileText className="h-3.5 w-3.5" />论文工作区</p><p className="mt-1 text-[10px] leading-4 text-muted">{paperFile.data ? `${activeLatexProject?.name} · ${paperFile.data.path} · v${paperFile.data.version}` : '尚未找到可读取的论文主文件'}</p></div>
              <Button size="sm" variant="secondary" disabled={!paperFile.data} onClick={() => paperFile.data && setManuscript(paperFile.data.content)}><RefreshCw className="mr-1 h-3 w-3" />载入</Button>
            </div>
          </div>
          <label className="mt-4 block text-xs font-medium text-text">稿件文本或结构化摘要
            <textarea value={manuscript} onChange={(event) => setManuscript(event.target.value)} className="mt-1 min-h-72 w-full resize-y border border-border-strong bg-surface p-3 font-mono text-xs leading-5" placeholder="可直接载入论文工作区，也可粘贴 abstract、method、experiments 与 limitations。" />
          </label>
          <button type="button" onClick={() => setIncludeExperiments((value) => !value)} className="mt-3 flex w-full items-center justify-between border border-border bg-surface-2/40 p-3 text-left">
            <span><span className="flex items-center gap-2 text-xs font-medium text-text"><FlaskConical className="h-3.5 w-3.5" />附加实验记录</span><span className="mt-1 block text-[10px] text-muted">{experimentEvidence.data?.length ?? 0} 个完成运行 · 指标原值</span></span>
            <span className={`flex h-5 w-5 items-center justify-center border ${includeExperiments ? 'border-success bg-success text-white' : 'border-border-strong'}`}>{includeExperiments && <CheckCircle2 className="h-3.5 w-3.5" />}</span>
          </button>
          <Button className="mt-4 w-full" onClick={() => start.mutate()} loading={start.isPending} disabled={!realProviderReady || manuscript.trim().length < 80 || experimentEvidence.isLoading}>
            <Sparkles className="h-4 w-4" />开始证据约束审稿
          </Button>
          <p className="mt-3 font-mono text-[9px] leading-4 text-faint">SKILL reviewer-challenger · {ideas.data?.total ?? 0} ideas · {runs.data?.length ?? 0} runs</p>
          {!realProviderReady && !configs.isLoading && <p className="mt-3 border border-warn/25 bg-warn-bg p-3 text-[10px] leading-4 text-warn">模拟审稿已锁定，避免 Mock 输出被误认成审稿意见。请先在<Link href={`/projects/${projectId}/manage?tab=settings`} className="mx-1 font-semibold underline">管理中心</Link>配置真实模型。</p>}
          {start.error && <p className="mt-3 border border-danger/20 bg-danger-bg p-3 text-xs text-danger">{start.error instanceof Error ? start.error.message : '启动失败'}</p>}
        </section>

        <section className="min-h-[38rem] border border-border bg-surface shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-4"><h2 className="text-sm font-semibold text-text">02 · 审稿报告与修改优先级</h2>{run.data && <span className="font-mono text-[10px] uppercase text-faint">{run.data.status}</span>}</div>
          <div className="p-5">
            {!runId && <div className="flex min-h-[28rem] flex-col items-center justify-center text-center"><AlertTriangle className="h-7 w-7 text-warn" /><p className="mt-4 max-w-md text-sm leading-7 text-muted">报告会逐条检查主张是否被稿件与实验数据支撑，区分致命有效性问题、证据缺口和表达改进，并给出至少两个 Reviewer-Challenger 深挖问题。</p></div>}
            {run.data && ['queued', 'running'].includes(run.data.status) && <div className="flex items-center gap-2 border border-info/20 bg-info-bg p-4 text-sm text-info"><Loader2 className="h-4 w-4 animate-spin" />Reviewer Agent 正在核对论文与实验记录…</div>}
            {run.data?.status === 'failed' && <div className="border border-danger/20 bg-danger-bg p-4 text-sm text-danger">{run.data.error_json?.message || '评审失败，请在管理中心测试模型连接。'}</div>}
            {run.data?.status === 'completed' && <article className="whitespace-pre-wrap text-sm leading-7 text-text">{typeof output === 'string' ? output : '运行完成，但没有返回文本报告。'}</article>}
          </div>
        </section>
      </div>
    </div>
  );
}

function reviewerPrompt(input: { venue: string; manuscript: string; ideas: Array<{ title: string; hypothesis: string | null; description: string }>; experiments: Array<{ run: { id: string; name: string; git_commit: string | null; config_json: Record<string, unknown> }; metrics: Array<{ name: string; step: number; value: number }> }> }): string {
  const evidence = {
    research_ideas: input.ideas.slice(0, 12),
    completed_experiment_runs: input.experiments.map((item) => ({
      run_id: item.run.id,
      name: item.run.name,
      git_commit: item.run.git_commit,
      config: item.run.config_json,
      recorded_metrics: item.metrics.slice(-120),
    })),
  };
  const prompt = `Use the active Reviewer Challenger skill. Simulate an independent review for ${input.venue}, but do not predict acceptance. Review ONLY the manuscript and project evidence below. Return in Chinese: 1) desk/scope check; 2) paper summary and claimed contributions; 3) claim-to-evidence table with [SUPPORTED], [PARTIAL], or [EVIDENCE GAP]; 4) strengths; 5) fatal validity threats; 6) major and minor weaknesses; 7) missing baselines, controls, ablations, statistical tests and reproducibility details; 8) at least two depth challenges; 9) prioritized revision plan with concrete manuscript or experiment actions; 10) simulated rubric score and confidence, explicitly labeled as non-predictive advice. Never invent citations, numbers, results, sections, or files.\n\nMANUSCRIPT:\n${input.manuscript.slice(0, 6800)}\n\nPROJECT EVIDENCE:\n${JSON.stringify(evidence).slice(0, 2600)}`;
  return prompt.slice(0, 9800);
}
