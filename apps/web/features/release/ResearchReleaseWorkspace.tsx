'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  CheckCircle2,
  FileCode2,
  FileText,
  GitCommit,
  Image,
  Loader2,
  Megaphone,
  PackageCheck,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { createAgentRun, getAgentRun } from '@/lib/api/agents';
import { getFile, listLatexProjects } from '@/lib/api/documents';
import { listMetrics, listProjectRuns } from '@/lib/api/experiments';
import { listIdeas } from '@/lib/api/ideas';
import { listLLMConfigs } from '@/lib/api/llmConfig';
import { getPatch, applyPatch } from '@/lib/api/patches';
import { listPapers } from '@/lib/api/papers';
import { getProject } from '@/lib/api/projects';

type ReleaseKind = 'website' | 'readme' | 'poster';

const RELEASES: Array<{ kind: ReleaseKind; title: string; eyebrow: string; description: string; paths: string; icon: typeof FileCode2 }> = [
  { kind: 'website', title: '项目宣传页', eyebrow: 'PROJECT PAGE', description: '生成无框架依赖的响应式学术项目页，并准备 GitHub Pages 工作流。', paths: 'page/* · .github/workflows/pages.yml', icon: FileCode2 },
  { kind: 'readme', title: 'GitHub README', eyebrow: 'REPOSITORY STORY', description: '把问题、贡献、复现步骤和已核验结果整理成仓库首页。', paths: 'README.md', icon: FileText },
  { kind: 'poster', title: '学术 Poster', eyebrow: 'LATEX POSTER', description: '生成结构清晰、图表优先、可编译的 LaTeX 海报源文件。', paths: 'poster/poster.tex · poster/README.md', icon: Image },
];

export function ResearchReleaseWorkspace({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<ReleaseKind>('website');
  const [storyPack, setStoryPack] = useState('');
  const [storyEdited, setStoryEdited] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const selected = RELEASES.find((item) => item.kind === kind)!;

  const project = useQuery({ queryKey: ['project', projectId], queryFn: () => getProject(projectId) });
  const papers = useQuery({ queryKey: ['papers', projectId, 'release'], queryFn: () => listPapers(projectId, { limit: 50 }) });
  const ideas = useQuery({ queryKey: ['ideas', projectId, 'release'], queryFn: () => listIdeas(projectId, { limit: 20 }) });
  const runs = useQuery({ queryKey: ['project-runs', projectId], queryFn: () => listProjectRuns(projectId) });
  const configs = useQuery({ queryKey: ['llm-configs', projectId], queryFn: () => listLLMConfigs(projectId) });
  const latexProjects = useQuery({ queryKey: ['latex-projects', projectId], queryFn: () => listLatexProjects(projectId) });
  const latexProject = latexProjects.data?.[0];
  const paperFile = useQuery({
    queryKey: ['release-paper-file', projectId, latexProject?.id],
    queryFn: () => getFile(projectId, latexProject!.id, latexProject!.main_file_path),
    enabled: Boolean(latexProject),
    retry: false,
  });
  const evidence = useQuery({
    queryKey: ['release-run-evidence', projectId, runs.data?.map((item) => item.id).join(',')],
    queryFn: async () => Promise.all((runs.data ?? []).filter((item) => item.status === 'completed').slice(0, 8).map(async (item) => ({ run: item, metrics: await listMetrics(projectId, item.id) }))),
    enabled: Boolean(runs.data),
  });
  const generatedPack = useMemo(() => buildStoryPack({
    project: project.data,
    papers: papers.data?.items ?? [],
    ideas: ideas.data?.items ?? [],
    evidence: evidence.data ?? [],
    manuscript: paperFile.data?.content ?? '',
  }), [project.data, papers.data, ideas.data, evidence.data, paperFile.data]);

  useEffect(() => {
    if (!storyEdited && generatedPack) setStoryPack(generatedPack);
  }, [generatedPack, storyEdited]);

  const realProviderReady = Boolean(configs.data?.some((item) => item.is_active));
  const start = useMutation({
    mutationFn: () => createAgentRun(projectId, { agent_type: 'coding', message: releasePrompt(kind, storyPack) }),
    onSuccess: (result) => setRunId(result.agent_run_id),
  });
  const run = useQuery({
    queryKey: ['release-run', projectId, runId],
    queryFn: () => getAgentRun(projectId, runId!),
    enabled: Boolean(runId),
    refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1500 : false,
  });
  const patchId = typeof run.data?.output_json?.patch_id === 'string' ? run.data.output_json.patch_id : null;
  const patch = useQuery({
    queryKey: ['workspace-patch', projectId, patchId],
    queryFn: () => getPatch(projectId, patchId!),
    enabled: Boolean(patchId),
  });
  const apply = useMutation({
    mutationFn: () => applyPatch(projectId, patchId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['workspace-patch', projectId, patchId] });
      void queryClient.invalidateQueries({ queryKey: ['workspace-tree', projectId] });
    },
  });

  return (
    <div className="-m-6 min-h-[calc(100dvh-3.5rem)] bg-bg lg:-m-8">
      <header className="mission-grid border-b border-border bg-surface px-6 py-8 lg:px-8">
        <Badge variant="neutral" size="sm">RESEARCH RELEASE STUDIO</Badge>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-5">
          <div><h1 className="flex items-center gap-3 text-3xl font-semibold tracking-[-0.04em] text-text"><Megaphone className="h-7 w-7 text-accent" />成果发布</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted">一份可核验的 Research Story Pack，生成宣传页、README 与学术 Poster。所有文件先进入补丁审查，再由你确认写入项目工作区。</p></div>
          <div className="flex items-center gap-2 border border-border bg-surface/80 px-4 py-3 text-xs"><span className={`h-2 w-2 rounded-full ${realProviderReady ? 'bg-success' : 'bg-warn'}`} /><span className="text-muted">{realProviderReady ? '真实模型连接已配置' : '未配置真实模型，生成已锁定'}</span></div>
        </div>
      </header>

      <div className="p-6 lg:p-8">
        <div className="grid gap-3 md:grid-cols-3">
          {RELEASES.map((item) => {
            const Icon = item.icon;
            return <button key={item.kind} type="button" onClick={() => { setKind(item.kind); setRunId(null); }} className={`group border p-5 text-left ${kind === item.kind ? 'border-accent bg-accent/5 shadow-sm' : 'border-border bg-surface hover:border-border-strong'}`}><div className="flex items-start justify-between"><span className="text-[9px] font-semibold tracking-[0.16em] text-faint">{item.eyebrow}</span><Icon className={`h-4 w-4 ${kind === item.kind ? 'text-accent' : 'text-muted'}`} /></div><h2 className="mt-5 text-base font-semibold text-text">{item.title}</h2><p className="mt-2 text-xs leading-5 text-muted">{item.description}</p><p className="mt-4 font-mono text-[9px] text-faint">{item.paths}</p></button>;
          })}
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[30rem_minmax(0,1fr)]">
          <section className="h-fit border border-border bg-surface shadow-sm">
            <div className="flex items-center justify-between border-b border-border px-5 py-4"><h2 className="flex items-center gap-2 text-sm font-semibold text-text"><PackageCheck className="h-4 w-4 text-accent" />唯一事实包</h2><button type="button" onClick={() => { setStoryEdited(false); setStoryPack(generatedPack); }} className="flex items-center gap-1 text-[10px] font-medium text-muted hover:text-text"><RefreshCw className="h-3 w-3" />从项目重新汇总</button></div>
            <div className="p-5">
              <textarea value={storyPack} onChange={(event) => { setStoryPack(event.target.value); setStoryEdited(true); }} className="min-h-[31rem] w-full resize-y border border-border-strong bg-bg p-3 font-mono text-[11px] leading-5 text-text" />
              {!realProviderReady && <div className="mt-3 flex items-start gap-2 border border-warn/25 bg-warn-bg p-3 text-xs leading-5 text-warn"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" /><span>系统不会使用 Mock LLM 伪造发布资产。请先在<Link className="mx-1 font-semibold underline" href={`/projects/${projectId}/manage?tab=settings`}>管理中心</Link>配置并测试真实模型。</span></div>}
              <Button className="mt-3 w-full" onClick={() => start.mutate()} loading={start.isPending} disabled={!realProviderReady || storyPack.trim().length < 120}>生成 {selected.title} 补丁</Button>
              <p className="mt-3 text-[10px] leading-4 text-faint">事实包中的 TODO 会保留为 TODO；Agent 不得补写未知作者、链接、指标、引用或奖项。</p>
              {start.error && <p className="mt-3 border border-danger/20 bg-danger-bg p-3 text-xs text-danger">{start.error instanceof Error ? start.error.message : '启动失败'}</p>}
            </div>
          </section>

          <section className="min-h-[38rem] border border-border bg-surface shadow-sm">
            <div className="flex items-center justify-between border-b border-border px-5 py-4"><h2 className="text-sm font-semibold text-text">{selected.title} · 补丁审查</h2>{run.data && <span className="font-mono text-[10px] uppercase text-faint">{run.data.status}</span>}</div>
            <div className="p-5">
              {!runId && <div className="flex min-h-[28rem] flex-col items-center justify-center text-center"><selected.icon className="h-8 w-8 text-accent" /><p className="mt-4 max-w-md text-sm leading-7 text-muted">Agent 会先读取当前工作区，再只针对 <span className="font-mono text-text">{selected.paths}</span> 形成可审查补丁。不会自动覆盖已有文件。</p></div>}
              {run.data && ['queued', 'running'].includes(run.data.status) && <div className="flex items-center gap-2 border border-info/20 bg-info-bg p-4 text-sm text-info"><Loader2 className="h-4 w-4 animate-spin" />Coding Agent 正在检查工作区并生成文件…</div>}
              {run.data?.status === 'failed' && <div className="border border-danger/20 bg-danger-bg p-4 text-sm text-danger">{run.data.error_json?.message || '生成失败，请检查模型连接、Worker 与工作区。'}</div>}
              {run.data?.status === 'completed' && !patchId && <div className="border border-warn/25 bg-warn-bg p-4 text-sm text-warn">运行完成但没有形成有效补丁；系统没有把文本回复冒充为文件。</div>}
              {patch.data && <div><div className="flex items-start justify-between gap-4 border-l-2 border-accent pl-4"><div><p className="text-sm font-semibold text-text">{patch.data.summary}</p><p className="mt-1 font-mono text-[10px] text-faint">PATCH {patch.data.id} · {patch.data.status}</p></div>{patch.data.status === 'pending' && <Button size="sm" onClick={() => apply.mutate()} loading={apply.isPending}>审核并应用全部文件</Button>}</div><div className="mt-5 space-y-2">{patch.data.files.map((file) => <div key={file.id} className="flex items-center justify-between border border-border bg-bg px-4 py-3"><span className="font-mono text-xs text-text">{file.path}</span><span className={`text-[9px] font-semibold uppercase ${file.change_type === 'delete' ? 'text-danger' : file.change_type === 'create' ? 'text-success' : 'text-info'}`}>{file.change_type}</span></div>)}</div>{patch.data.status === 'applied' && <div className="mt-5 flex items-start gap-3 border border-success/25 bg-success-bg p-4 text-sm text-success"><CheckCircle2 className="mt-0.5 h-4 w-4" /><div><p className="font-semibold">文件已写入项目工作区</p><p className="mt-1 flex items-center gap-1 font-mono text-[10px]"><GitCommit className="h-3 w-3" />{patch.data.applied_commit_sha ?? '当前目录未生成 Git commit'}</p></div></div>}<Link href={`/projects/${projectId}/ide`} className="mt-5 inline-flex items-center gap-2 text-xs font-semibold text-accent hover:underline">在 AI IDE 中逐文件查看 <ArrowRight className="h-3.5 w-3.5" /></Link></div>}
              {apply.error && <p className="mt-4 border border-danger/20 bg-danger-bg p-3 text-xs text-danger">{apply.error instanceof Error ? apply.error.message : '应用补丁失败'}</p>}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function buildStoryPack(input: { project?: { name: string; description: string | null; field: string | null }; papers: Array<{ title: string; authors_json: string[]; venue: string | null; published_at: string | null; doi: string | null; url: string }>; ideas: Array<{ title: string; description: string; hypothesis: string | null }>; evidence: Array<{ run: { id: string; name: string; git_commit: string | null; config_json: Record<string, unknown> }; metrics: Array<{ name: string; step: number; value: number }> }>; manuscript: string }): string {
  if (!input.project) return '';
  const results = input.evidence.map(({ run, metrics }) => {
    const latest = new Map<string, { step: number; value: number }>();
    for (const metric of metrics) {
      const current = latest.get(metric.name);
      if (!current || metric.step >= current.step) latest.set(metric.name, { step: metric.step, value: metric.value });
    }
    return { run_id: run.id, name: run.name, commit: run.git_commit ?? 'TODO', latest_recorded_metrics: Object.fromEntries(latest), config: run.config_json };
  });
  return `# RESEARCH STORY PACK — AUTO-GENERATED FROM PERSISTED PROJECT DATA
Project: ${input.project.name}
Field: ${input.project.field ?? 'TODO'}
One-line hook: ${input.project.description ?? 'TODO'}
Authors / affiliations: TODO
Paper / Code / Model / Demo links: TODO

## Research ideas and hypotheses
${input.ideas.length ? input.ideas.map((idea, index) => `${index + 1}. ${idea.title}\n   Hypothesis: ${idea.hypothesis ?? 'TODO'}\n   ${idea.description}`).join('\n') : 'TODO'}

## Verified experiment records
${results.length ? JSON.stringify(results, null, 2) : 'TODO — no completed run with recorded metrics'}

## Literature already in the project library
${input.papers.length ? input.papers.slice(0, 25).map((paper) => `- ${paper.title} — ${paper.authors_json.join(', ') || 'unknown authors'}; ${paper.venue ?? 'venue unknown'}; ${paper.published_at?.slice(0, 4) ?? 'year unknown'}; ${paper.doi ?? paper.url}`).join('\n') : 'TODO'}

## Manuscript excerpt
${input.manuscript ? input.manuscript.slice(0, 2400) : 'TODO — no paper workspace manuscript'}

## Claims, contribution wording, reusable figures, limitations, BibTeX
TODO — review and complete from the manuscript before publishing.`.slice(0, 9000);
}

function releasePrompt(kind: ReleaseKind, storyPack: string): string {
  const requirements: Record<ReleaseKind, string> = {
    website: `Create or update ONLY these assets: page/index.html, page/styles.css, optional page/app.js, and .github/workflows/pages.yml. The workflow must publish the page directory with GitHub Pages actions. Build a responsive static academic project page with no build step and no external UI framework. Visual direction: near-black editorial canvas, restrained research-green/mint accent, fine evidence-grid texture, strong typographic hierarchy, compact hero, method pipeline, verified result cards, limitations, BibTeX, and accessible focus/contrast. Avoid gradients, giant slogan text, excessive rounded cards, fake charts, and decorative clutter. Use semantic HTML, descriptive alt text, and reduced-motion support.`,
    readme: `Create or update ONLY README.md. Read it before modifying it. Produce an honest research repository README with title, one-line problem, status badges only when verifiable, contribution list, method overview, verified results table, quick start using commands that actually exist in the workspace, project structure, reproducibility checklist, limitations, citation, and license/TODO. Do not erase valuable existing installation or contribution information.`,
    poster: `Create or update ONLY poster/poster.tex and poster/README.md. Generate a self-contained beamerposter source with a restrained dark/green or print-safe light palette, clear 3-column hierarchy, large but not oversized title, problem/method/results/limitations/references blocks, and explicit TODO placeholders for missing figures. The README must contain exact compile instructions and asset placement guidance. Never create fake plots or results.`,
  };
  return `You are preparing a publication-grade research release. Inspect the workspace before proposing changes. ${requirements[kind]} Use ONLY the factual Research Story Pack below. Never invent metrics, citations, authors, affiliations, awards, links, commands, demos, filenames, or qualitative claims. Preserve TODO for missing evidence. Return the required coding-agent JSON patch proposal, not prose.\n\nRESEARCH STORY PACK:\n${storyPack.slice(0, 8200)}`.slice(0, 9800);
}
