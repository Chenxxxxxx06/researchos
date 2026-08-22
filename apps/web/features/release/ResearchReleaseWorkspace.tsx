'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  CheckCircle2,
  Download,
  ExternalLink,
  FileCode2,
  FileText,
  GitCommit,
  Globe2,
  Image,
  Loader2,
  Megaphone,
  PackageCheck,
  Presentation,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState, type ReactNode } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { createAgentRun, getAgentRun } from '@/lib/api/agents';
import { getFile, listLatexProjects } from '@/lib/api/documents';
import { listMetrics, listProjectRuns } from '@/lib/api/experiments';
import { listIdeas } from '@/lib/api/ideas';
import { listLLMConfigs } from '@/lib/api/llmConfig';
import { applyPatch, getPatch } from '@/lib/api/patches';
import { listPapers } from '@/lib/api/papers';
import { getProject } from '@/lib/api/projects';
import {
  cancelReleaseJob,
  createReleaseJob,
  getReleaseIntegration,
  getReleaseJob,
  listReleaseJobs,
  type AutoDesignArtifact,
  type ReleaseJob,
} from '@/lib/api/releases';

type ReleaseKind = 'website' | 'readme' | 'poster' | 'slides';

interface ReleaseDefinition {
  kind: ReleaseKind;
  title: string;
  eyebrow: string;
  description: string;
  paths: string;
  icon: typeof FileCode2;
  engine: 'autodesign' | 'coding-agent';
}

const RELEASES: ReleaseDefinition[] = [
  {
    kind: 'website',
    title: '项目宣传页',
    eyebrow: 'EDITABLE WEBPAGE',
    description: '由 AutoDesign 把论文证据组织为可编辑、可预览的学术项目网页。',
    paths: 'AutoDesign/out/runs/<id>/final/index.html',
    icon: Globe2,
    engine: 'autodesign',
  },
  {
    kind: 'readme',
    title: 'GitHub README',
    eyebrow: 'REPOSITORY STORY',
    description: '把问题、贡献、复现步骤和已核验结果整理成仓库首页补丁。',
    paths: 'Workspace/README.md',
    icon: FileText,
    engine: 'coding-agent',
  },
  {
    kind: 'poster',
    title: '学术 Poster',
    eyebrow: 'EDITABLE POSTER',
    description: '由 AutoDesign DesignHarness 生成可编辑海报、预览图和 PDF。',
    paths: 'AutoDesign/out/runs/<id>/final/poster.*',
    icon: Image,
    engine: 'autodesign',
  },
  {
    kind: 'slides',
    title: '会议 Slides',
    eyebrow: 'CONFERENCE DECK',
    description: '从同一事实包生成可编辑演示文稿、PDF 与页面预览。',
    paths: 'AutoDesign/out/runs/<id>/final/deck.*',
    icon: Presentation,
    engine: 'autodesign',
  },
];

export function ResearchReleaseWorkspace({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<ReleaseKind>('website');
  const [storyPack, setStoryPack] = useState('');
  const [storyEdited, setStoryEdited] = useState(false);
  const [agentRunId, setAgentRunId] = useState<string | null>(null);
  const [autoDesignJobId, setAutoDesignJobId] = useState<string | null>(null);
  const selected = RELEASES.find((item) => item.kind === kind)!;

  const sharedQuery = { staleTime: 30_000, refetchOnMount: false as const };
  const project = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    ...sharedQuery,
  });
  const papers = useQuery({
    queryKey: ['papers', projectId, 'release'],
    queryFn: () => listPapers(projectId, { limit: 50 }),
    ...sharedQuery,
  });
  const ideas = useQuery({
    queryKey: ['ideas', projectId, 'release'],
    queryFn: () => listIdeas(projectId, { limit: 20 }),
    ...sharedQuery,
  });
  const runs = useQuery({
    queryKey: ['project-runs', projectId],
    queryFn: () => listProjectRuns(projectId),
    ...sharedQuery,
  });
  const configs = useQuery({
    queryKey: ['llm-configs', projectId],
    queryFn: () => listLLMConfigs(projectId),
    staleTime: 15_000,
  });
  const qwenConfig = configs.data?.find(
    (item) => item.is_active && item.model.trim().toLowerCase() === 'qwen-plus',
  );
  const integration = useQuery({
    queryKey: ['release-integration', projectId],
    queryFn: () => getReleaseIntegration(projectId),
    enabled: Boolean(qwenConfig),
    staleTime: 10_000,
    retry: 0,
  });
  const releaseJobs = useQuery({
    queryKey: ['release-jobs', projectId],
    queryFn: () => listReleaseJobs(projectId),
    staleTime: 5_000,
  });
  const latexProjects = useQuery({
    queryKey: ['latex-projects', projectId],
    queryFn: () => listLatexProjects(projectId),
    ...sharedQuery,
  });
  const latexProject = latexProjects.data?.[0];
  const paperFile = useQuery({
    queryKey: ['release-paper-file', projectId, latexProject?.id],
    queryFn: () => getFile(projectId, latexProject!.id, latexProject!.main_file_path),
    enabled: Boolean(latexProject),
    retry: false,
    ...sharedQuery,
  });
  const evidence = useQuery({
    queryKey: ['release-run-evidence', projectId, runs.data?.map((item) => item.id).join(',')],
    queryFn: async () =>
      Promise.all(
        (runs.data ?? [])
          .filter((item) => item.status === 'completed')
          .slice(0, 8)
          .map(async (item) => ({ run: item, metrics: await listMetrics(projectId, item.id) })),
      ),
    enabled: Boolean(runs.data),
    staleTime: 30_000,
  });
  const generatedPack = useMemo(
    () =>
      buildStoryPack({
        project: project.data,
        papers: papers.data?.items ?? [],
        ideas: ideas.data?.items ?? [],
        evidence: evidence.data ?? [],
        manuscript: paperFile.data?.content ?? '',
      }),
    [project.data, papers.data, ideas.data, evidence.data, paperFile.data],
  );

  useEffect(() => {
    if (!storyEdited && generatedPack) setStoryPack(generatedPack);
  }, [generatedPack, storyEdited]);

  const agentStart = useMutation({
    mutationFn: () =>
      createAgentRun(projectId, {
        agent_type: 'coding',
        message: readmePrompt(storyPack),
        context: { llm_config_id: qwenConfig!.id },
      }),
    onSuccess: (result) => setAgentRunId(result.agent_run_id),
  });
  const agentRun = useQuery({
    queryKey: ['release-agent-run', projectId, agentRunId],
    queryFn: () => getAgentRun(projectId, agentRunId!),
    enabled: Boolean(agentRunId),
    refetchInterval: (query) =>
      ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1200 : false,
  });
  const patchId =
    typeof agentRun.data?.output_json?.patch_id === 'string'
      ? agentRun.data.output_json.patch_id
      : null;
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

  const autoDesignStart = useMutation({
    mutationFn: () =>
      createReleaseJob(projectId, {
        kind: kind as 'website' | 'poster' | 'slides',
        story_pack: storyPack,
        ...(kind === 'poster' ? { template: 'cvpr-landscape' } : {}),
      }),
    onSuccess: (job) => {
      setAutoDesignJobId(job.id);
      queryClient.setQueryData(['release-job', projectId, job.id], job);
      void queryClient.invalidateQueries({ queryKey: ['release-jobs', projectId] });
    },
  });
  const activeAutoDesignJob = useQuery({
    queryKey: ['release-job', projectId, autoDesignJobId],
    queryFn: () => getReleaseJob(projectId, autoDesignJobId!),
    enabled: Boolean(autoDesignJobId),
    refetchInterval: (query) =>
      ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1200 : false,
  });
  const cancelAutoDesign = useMutation({
    mutationFn: () => cancelReleaseJob(projectId, autoDesignJobId!),
    onSuccess: (job) => {
      queryClient.setQueryData(['release-job', projectId, job.id], job);
      void queryClient.invalidateQueries({ queryKey: ['release-jobs', projectId] });
    },
  });

  useEffect(() => {
    if (activeAutoDesignJob.data && !['queued', 'running'].includes(activeAutoDesignJob.data.status)) {
      void queryClient.invalidateQueries({ queryKey: ['release-jobs', projectId] });
    }
  }, [activeAutoDesignJob.data, projectId, queryClient]);

  const canGenerate = Boolean(
    qwenConfig &&
      storyPack.trim().length >= 120 &&
      (selected.engine === 'coding-agent' || integration.data?.available),
  );
  const currentJob = activeAutoDesignJob.data;
  const start = () => {
    if (selected.engine === 'coding-agent') agentStart.mutate();
    else autoDesignStart.mutate();
  };

  return (
    <div className="-m-5 min-h-[calc(100dvh-4rem)] bg-bg lg:-m-6 xl:-m-8">
      <header className="mission-grid border-b border-border bg-surface px-6 py-8 lg:px-8">
        <Badge variant="neutral" size="sm">RESEARCH RELEASE STUDIO</Badge>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-5">
          <div>
            <h1 className="flex items-center gap-3 text-3xl font-semibold tracking-[-0.04em] text-text">
              <Megaphone className="h-7 w-7 text-accent" />成果发布
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              同一份可核验 Research Story Pack，生成 README 补丁以及 AutoDesign
              网页、海报和会议演示。所有生成模型固定为 qwen-plus。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip
              ok={Boolean(qwenConfig)}
              label={qwenConfig ? `qwen-plus · ${qwenConfig.name}` : '缺少启用的 qwen-plus'}
            />
            <StatusChip
              ok={Boolean(integration.data?.available)}
              label={
                integration.isLoading
                  ? '正在检查 AutoDesign'
                  : integration.data?.message ?? 'AutoDesign 尚未检查'
              }
            />
          </div>
        </div>
      </header>

      <div className="p-6 lg:p-8">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {RELEASES.map((item) => {
            const Icon = item.icon;
            const active = kind === item.kind;
            return (
              <button
                key={item.kind}
                type="button"
                aria-pressed={active}
                data-testid={`release-kind-${item.kind}`}
                onClick={() => {
                  setKind(item.kind);
                  setAgentRunId(null);
                  setAutoDesignJobId(null);
                }}
                className={`group border p-5 text-left transition duration-200 active:translate-y-px ${
                  active
                    ? 'border-accent bg-accent/5 shadow-sm'
                    : 'border-border bg-surface hover:-translate-y-0.5 hover:border-border-strong'
                }`}
              >
                <div className="flex items-start justify-between">
                  <span className="text-[9px] font-semibold tracking-[0.16em] text-faint">
                    {item.eyebrow}
                  </span>
                  <Icon className={`h-4 w-4 ${active ? 'text-accent' : 'text-muted'}`} />
                </div>
                <h2 className="mt-5 text-base font-semibold text-text">{item.title}</h2>
                <p className="mt-2 text-xs leading-5 text-muted">{item.description}</p>
                <p className="mt-4 break-all font-mono text-[9px] text-faint">{item.paths}</p>
              </button>
            );
          })}
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[30rem_minmax(0,1fr)]">
          <section className="h-fit border border-border bg-surface shadow-sm">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-text">
                <PackageCheck className="h-4 w-4 text-accent" />唯一事实包
              </h2>
              <button
                type="button"
                onClick={() => {
                  setStoryEdited(false);
                  setStoryPack(generatedPack);
                }}
                className="flex items-center gap-1 text-[10px] font-medium text-muted hover:text-text"
              >
                <RefreshCw className="h-3 w-3" />从项目重新汇总
              </button>
            </div>
            <div className="p-5">
              <textarea
                aria-label="Research Story Pack"
                value={storyPack}
                onChange={(event) => {
                  setStoryPack(event.target.value);
                  setStoryEdited(true);
                }}
                className="min-h-[31rem] w-full resize-y border border-border-strong bg-bg p-3 font-mono text-[11px] leading-5 text-text focus:border-accent focus:outline-none"
              />
              {!qwenConfig && (
                <Warning>
                  成果发布只使用 qwen-plus。请先在
                  <Link className="mx-1 font-semibold underline" href={`/projects/${projectId}/manage?tab=settings`}>
                    管理中心
                  </Link>
                  新建并启用该模型配置。
                </Warning>
              )}
              {qwenConfig && selected.engine === 'autodesign' && integration.data && !integration.data.available && (
                <Warning>
                  AutoDesign 服务未启动。请在仓库根目录运行
                  <code className="mx-1 rounded bg-warn/10 px-1.5 py-0.5">start-autodesign.cmd</code>
                  ，生成文件会保存在 AutoDesign 的 out/runs 目录。
                </Warning>
              )}
              <Button
                className="mt-3 w-full"
                onClick={start}
                loading={agentStart.isPending || autoDesignStart.isPending}
                disabled={!canGenerate}
              >
                {selected.engine === 'autodesign' ? <Sparkles className="mr-2 h-4 w-4" /> : null}
                生成 {selected.title}
              </Button>
              <p className="mt-3 text-[10px] leading-4 text-faint">
                未知作者、链接、指标、引用和奖项会保留为空缺；生成流程不得补造证据。
              </p>
              {(agentStart.error || autoDesignStart.error) && (
                <ErrorBox error={agentStart.error ?? autoDesignStart.error} />
              )}
            </div>
          </section>

          <section className="min-h-[38rem] border border-border bg-surface shadow-sm">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <h2 className="text-sm font-semibold text-text">{selected.title} · 生成与审查</h2>
              <span className="font-mono text-[10px] uppercase text-faint">
                {selected.engine === 'autodesign'
                  ? currentJob?.status ?? 'READY'
                  : agentRun.data?.status ?? 'READY'}
              </span>
            </div>
            {selected.engine === 'autodesign' ? (
              <AutoDesignRunPanel
                job={currentJob ?? null}
                selected={selected}
                cancelling={cancelAutoDesign.isPending}
                onCancel={() => cancelAutoDesign.mutate()}
              />
            ) : (
              <ReadmePatchPanel
                projectId={projectId}
                runId={agentRunId}
                run={agentRun.data}
                patch={patch.data}
                applyPending={apply.isPending}
                onApply={() => apply.mutate()}
                applyError={apply.error}
              />
            )}
          </section>
        </div>

        <ReleaseGallery
          jobs={releaseJobs.data ?? []}
          onOpen={(job) => {
            setKind(job.kind);
            setAutoDesignJobId(job.id);
          }}
        />
      </div>
    </div>
  );
}

function StatusChip({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 border border-border bg-surface/80 px-3 py-2 text-[10px]">
      <span className={`h-2 w-2 rounded-full ${ok ? 'bg-success' : 'bg-warn'}`} />
      <span className="text-muted">{label}</span>
    </div>
  );
}

function Warning({ children }: { children: ReactNode }) {
  return (
    <div className="mt-3 flex items-start gap-2 border border-warn/25 bg-warn-bg p-3 text-xs leading-5 text-warn">
      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{children}</span>
    </div>
  );
}

function ErrorBox({ error }: { error: unknown }) {
  return (
    <p className="mt-3 border border-danger/20 bg-danger-bg p-3 text-xs text-danger">
      {error instanceof Error ? error.message : '启动失败'}
    </p>
  );
}

function AutoDesignRunPanel({
  job,
  selected,
  cancelling,
  onCancel,
}: {
  job: ReleaseJob | null;
  selected: ReleaseDefinition;
  cancelling: boolean;
  onCancel: () => void;
}) {
  const artifact = job?.artifact_json?.artifact ?? null;
  if (!job) {
    const Icon = selected.icon;
    return (
      <div className="flex min-h-[32rem] flex-col items-center justify-center p-8 text-center">
        <Icon className="h-8 w-8 text-accent" />
        <p className="mt-4 max-w-md text-sm leading-7 text-muted">
          AutoDesign 会摄取当前事实包，通过 qwen-plus 生成原生可编辑文件，再执行布局与来源检查。
          任务创建后立即返回，进度和成果会在此处自动更新。
        </p>
      </div>
    );
  }
  if (['queued', 'running'].includes(job.status)) {
    return (
      <div className="p-5">
        <div className="flex items-start gap-3 border border-info/20 bg-info-bg p-4 text-sm text-info">
          <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">AutoDesign DesignHarness 正在运行</p>
            <p className="mt-1 text-xs leading-5">
              {String(job.progress_json.message ?? '正在生成并验证可编辑成果')}
            </p>
            {job.external_run_id && (
              <p className="mt-2 break-all font-mono text-[10px] opacity-75">
                integrations/AutoDesign/out/runs/{job.external_run_id}/final
              </p>
            )}
          </div>
          <Button size="sm" variant="ghost" onClick={onCancel} loading={cancelling}>
            <X className="mr-1 h-3.5 w-3.5" />取消
          </Button>
        </div>
        <div className="mt-5 grid grid-cols-4 gap-1" aria-label="Generation progress">
          {['摄取', '生成', '审查', '导出'].map((label, index) => (
            <div key={label} className="text-center">
              <div className={`h-1 ${index < 2 ? 'bg-accent' : 'bg-border'}`} />
              <span className="mt-2 block text-[9px] text-faint">{label}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (job.status === 'failed' || job.status === 'cancelled') {
    return (
      <div className="p-5">
        <div className="border border-danger/20 bg-danger-bg p-4 text-sm text-danger">
          {job.status === 'cancelled' ? '任务已取消。' : job.error_message ?? 'AutoDesign 生成失败。'}
        </div>
      </div>
    );
  }
  return <ArtifactViewer artifact={artifact} job={job} />;
}

function ArtifactViewer({ artifact, job }: { artifact: AutoDesignArtifact | null; job: ReleaseJob }) {
  if (!artifact) {
    return <div className="p-5 text-sm text-warn">任务已结束，但未返回可展示的成果元数据。</div>;
  }
  const preview = artifact.card_preview_url || artifact.preview_url;
  const view = artifact.view_file_url || artifact.native_file_url || artifact.pdf_url;
  const download = artifact.download_url || artifact.pdf_url || artifact.native_file_url;
  return (
    <div className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4 border-l-2 border-success pl-4">
        <div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-success" />
            <p className="text-sm font-semibold text-text">{artifact.name || 'AutoDesign 成果'}</p>
          </div>
          <p className="mt-1 font-mono text-[10px] text-faint">
            {job.model} · {artifact.native_format ?? artifact.artifact_type} · {job.external_run_id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {view && (
            <a
              href={view}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-8 items-center rounded-md border border-border px-2.5 text-xs font-medium text-muted transition hover:bg-surface-2 hover:text-text active:translate-y-px"
            >
              <ExternalLink className="mr-1 h-3.5 w-3.5" />预览
            </a>
          )}
          {download && (
            <a
              href={download}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-8 items-center rounded-md bg-accent px-3 text-xs font-medium text-accent-fg transition hover:brightness-105 active:translate-y-px"
            >
              <Download className="mr-1 h-3.5 w-3.5" />下载
            </a>
          )}
        </div>
      </div>
      {preview ? (
        <a href={view ?? preview} target="_blank" rel="noreferrer" className="mt-5 block overflow-hidden border border-border bg-bg">
          {/* AutoDesign returns a rendered artifact URL; the factual content remains source-grounded. */}
          <img src={preview} alt={`${artifact.name} preview`} className="max-h-[34rem] w-full object-contain" />
        </a>
      ) : view && artifact.view_format === 'html' ? (
        <iframe title={`${artifact.name} preview`} src={view} className="mt-5 h-[34rem] w-full border border-border bg-white" />
      ) : null}
      <div className="mt-4 border border-border bg-bg px-4 py-3">
        <p className="text-[10px] font-medium text-muted">本地输出目录</p>
        <p className="mt-1 break-all font-mono text-[10px] text-text">
          integrations/AutoDesign/out/runs/{job.external_run_id}/final
        </p>
      </div>
      {artifact.quality_diagnostics && artifact.quality_diagnostics.length > 0 && (
        <ul className="mt-4 space-y-1 border border-warn/20 bg-warn-bg p-3 text-xs text-warn">
          {artifact.quality_diagnostics.map((item) => <li key={item}>• {item}</li>)}
        </ul>
      )}
    </div>
  );
}

function ReadmePatchPanel({
  projectId,
  runId,
  run,
  patch,
  applyPending,
  onApply,
  applyError,
}: {
  projectId: string;
  runId: string | null;
  run: Awaited<ReturnType<typeof getAgentRun>> | undefined;
  patch: Awaited<ReturnType<typeof getPatch>> | undefined;
  applyPending: boolean;
  onApply: () => void;
  applyError: unknown;
}) {
  if (!runId) {
    return (
      <div className="flex min-h-[32rem] flex-col items-center justify-center p-8 text-center">
        <FileText className="h-8 w-8 text-accent" />
        <p className="mt-4 max-w-md text-sm leading-7 text-muted">
          Coding Agent 会先读取现有 README，再使用 qwen-plus 形成只修改 README.md
          的可审查补丁，不会自动覆盖仓库。
        </p>
      </div>
    );
  }
  return (
    <div className="p-5">
      {run && ['queued', 'running'].includes(run.status) && (
        <div className="flex items-center gap-2 border border-info/20 bg-info-bg p-4 text-sm text-info">
          <Loader2 className="h-4 w-4 animate-spin" />Coding Agent 正在检查工作区并生成 README 补丁…
        </div>
      )}
      {run?.status === 'failed' && (
        <div className="border border-danger/20 bg-danger-bg p-4 text-sm text-danger">
          {run.error_json?.message || '生成失败，请检查 qwen-plus、Worker 与工作区。'}
        </div>
      )}
      {run?.status === 'completed' && !patch && (
        <div className="border border-warn/25 bg-warn-bg p-4 text-sm text-warn">
          运行完成但没有形成有效补丁；系统没有把文本回复冒充为文件。
        </div>
      )}
      {patch && (
        <div>
          <div className="flex items-start justify-between gap-4 border-l-2 border-accent pl-4">
            <div>
              <p className="text-sm font-semibold text-text">{patch.summary}</p>
              <p className="mt-1 font-mono text-[10px] text-faint">PATCH {patch.id} · {patch.status}</p>
            </div>
            {patch.status === 'pending' && (
              <Button size="sm" onClick={onApply} loading={applyPending}>审核并应用</Button>
            )}
          </div>
          <div className="mt-5 space-y-2">
            {patch.files.map((file) => (
              <div key={file.id} className="flex items-center justify-between border border-border bg-bg px-4 py-3">
                <span className="font-mono text-xs text-text">{file.path}</span>
                <span className="text-[9px] font-semibold uppercase text-info">{file.change_type}</span>
              </div>
            ))}
          </div>
          {patch.status === 'applied' && (
            <div className="mt-5 flex items-start gap-3 border border-success/25 bg-success-bg p-4 text-sm text-success">
              <CheckCircle2 className="mt-0.5 h-4 w-4" />
              <div>
                <p className="font-semibold">README 已写入项目工作区</p>
                <p className="mt-1 flex items-center gap-1 font-mono text-[10px]">
                  <GitCommit className="h-3 w-3" />{patch.applied_commit_sha ?? '工作区未启用 Git commit'}
                </p>
              </div>
            </div>
          )}
          <Link href={`/projects/${projectId}/ide`} className="mt-5 inline-flex items-center gap-2 text-xs font-semibold text-accent hover:underline">
            在 AI IDE 中逐文件查看 <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}
      {Boolean(applyError) && <ErrorBox error={applyError} />}
    </div>
  );
}

function ReleaseGallery({ jobs, onOpen }: { jobs: ReleaseJob[]; onOpen: (job: ReleaseJob) => void }) {
  if (jobs.length === 0) return null;
  return (
    <section className="mt-8 border-t border-border pt-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[9px] font-semibold tracking-[0.16em] text-faint">AUTODESIGN OUTPUTS</p>
          <h2 className="mt-2 text-lg font-semibold text-text">生成历史</h2>
        </div>
        <p className="text-xs text-muted">成果保存在 AutoDesign 运行目录，记录保存在 ResearchOS。</p>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {jobs.slice(0, 9).map((job) => {
          const artifact = job.artifact_json?.artifact;
          const preview = artifact?.card_preview_url || artifact?.preview_url;
          return (
            <button
              key={job.id}
              type="button"
              onClick={() => onOpen(job)}
              className="group overflow-hidden border border-border bg-surface text-left transition hover:-translate-y-0.5 hover:border-border-strong"
            >
              <div className="aspect-[16/9] overflow-hidden bg-bg">
                {preview ? (
                  <img src={preview} alt="" className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]" />
                ) : (
                  <div className="flex h-full items-center justify-center"><Megaphone className="h-6 w-6 text-faint" /></div>
                )}
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-semibold text-text">{artifact?.name ?? releaseKindLabel(job.kind)}</span>
                  <Badge variant={job.status === 'succeeded' ? 'success' : job.status === 'failed' ? 'danger' : 'neutral'} size="sm">
                    {job.status}
                  </Badge>
                </div>
                <p className="mt-2 font-mono text-[9px] text-faint">qwen-plus · {job.external_run_id ?? job.id}</p>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function releaseKindLabel(kind: string): string {
  return { website: '项目宣传页', poster: '学术 Poster', slides: '会议 Slides' }[kind] ?? kind;
}

function buildStoryPack(input: {
  project?: { name: string; description: string | null; field: string | null };
  papers: Array<{
    title: string;
    authors_json: string[];
    venue: string | null;
    published_at: string | null;
    doi: string | null;
    url: string;
  }>;
  ideas: Array<{ title: string; description: string; hypothesis: string | null }>;
  evidence: Array<{
    run: { id: string; name: string; git_commit: string | null; config_json: Record<string, unknown> };
    metrics: Array<{ name: string; step: number; value: number }>;
  }>;
  manuscript: string;
}): string {
  if (!input.project) return '';
  const results = input.evidence.map(({ run, metrics }) => {
    const latest = new Map<string, { step: number; value: number }>();
    for (const metric of metrics) {
      const current = latest.get(metric.name);
      if (!current || metric.step >= current.step) latest.set(metric.name, { step: metric.step, value: metric.value });
    }
    return {
      run_id: run.id,
      name: run.name,
      commit: run.git_commit ?? 'not recorded',
      latest_recorded_metrics: Object.fromEntries(latest),
      config: run.config_json,
    };
  });
  return `# RESEARCH STORY PACK — GENERATED FROM PERSISTED PROJECT DATA
Project: ${input.project.name}
Field: ${input.project.field ?? 'not provided'}
One-line hook: ${input.project.description ?? 'not provided'}
Authors / affiliations: not provided
Paper / Code / Model / Demo links: not provided

## Research ideas and hypotheses
${input.ideas.length ? input.ideas.map((idea, index) => `${index + 1}. ${idea.title}\n   Hypothesis: ${idea.hypothesis ?? 'not provided'}\n   ${idea.description}`).join('\n') : 'No research idea has been persisted.'}

## Verified experiment records
${results.length ? JSON.stringify(results, null, 2) : 'No completed run with recorded metrics.'}

## Literature already in the project library
${input.papers.length ? input.papers.slice(0, 25).map((paper) => `- ${paper.title} — ${paper.authors_json.join(', ') || 'authors not recorded'}; ${paper.venue ?? 'venue not recorded'}; ${paper.published_at?.slice(0, 4) ?? 'year not recorded'}; ${paper.doi ?? paper.url}`).join('\n') : 'No literature record has been persisted.'}

## Manuscript excerpt
${input.manuscript ? input.manuscript.slice(0, 5000) : 'No LaTeX manuscript has been created.'}

## Evidence policy
Use only the records above. Mark missing claims, contribution wording, reusable figures, limitations, and BibTeX as not provided.`.slice(0, 16_000);
}

function readmePrompt(storyPack: string): string {
  return `You are preparing an evidence-bound research repository release. Inspect the workspace before proposing changes. Create or update ONLY README.md. Read it before modifying it. Produce an honest README with a title, one-line problem, badges only when verifiable, contributions, method overview, verified results table, exact quick-start commands that exist in the workspace, project structure, reproducibility checklist, limitations, citation, and license status. Preserve valuable existing installation and contribution information. Use only the Research Story Pack below. Never invent metrics, citations, authors, affiliations, awards, links, commands, demos, or filenames. Return the coding-agent JSON patch proposal, not prose.\n\nRESEARCH STORY PACK:\n${storyPack.slice(0, 9000)}`.slice(0, 9800);
}
