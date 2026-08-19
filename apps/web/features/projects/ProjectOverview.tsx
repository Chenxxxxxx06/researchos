'use client';

import { useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  Code2,
  FileText,
  FlaskConical,
  Inbox,
  Megaphone,
  Route,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api/client';
import { listInboxItems } from '@/lib/api/inbox';
import { getManagementSummary } from '@/lib/api/management';
import { listMissions } from '@/lib/api/missions';
import { getProject, type Project } from '@/lib/api/projects';
import { useI18n } from '@/lib/i18n';

export function ProjectOverview({ projectId }: { projectId: string }) {
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const project = useQuery<Project, ApiError>({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });
  const management = useQuery({
    queryKey: ['management-summary', projectId],
    queryFn: () => getManagementSummary(projectId),
  });
  const missions = useQuery({
    queryKey: ['missions', projectId],
    queryFn: () => listMissions(projectId),
  });
  const inbox = useQuery({
    queryKey: ['inbox-items', projectId],
    queryFn: () => listInboxItems(projectId),
  });

  if (project.isLoading) return <Skeleton className="h-[36rem] w-full" />;
  if (project.isError) {
    return <Card><CardContent className="p-6"><p className="text-sm text-danger">{project.error.status === 404 ? (zh ? '项目不存在。' : 'Project not found.') : project.error.message}</p></CardContent></Card>;
  }
  if (!project.data) return null;

  const counts = management.data?.counts;
  const missionItems = missions.data?.items ?? [];
  const latestMission = [...missionItems].sort((a, b) => b.last_activity_at.localeCompare(a.last_activity_at))[0];
  const inboxCount = inbox.data?.length ?? 0;
  const activeMissions = missionItems.filter((item) => item.status === 'active').length;
  const flow = [
    {
      index: '01',
      icon: Inbox,
      title: zh ? '收集研究材料' : 'Capture research input',
      description: zh ? '上传 PDF、DOCX、文本或音频，提取内容并交给 Agent 归纳。' : 'Upload PDF, DOCX, text, or audio; extract it and hand it to the agent.',
      href: `/projects/${projectId}/inbox`,
      evidence: zh ? `${inboxCount} 条收件箱材料` : `${inboxCount} inbox items`,
      ready: inboxCount > 0,
    },
    {
      index: '02',
      icon: BookOpen,
      title: zh ? '建立文献证据库' : 'Build the evidence library',
      description: zh ? '同步 Zotero、检索文献并沉淀结构化阅读卡与引用证据。' : 'Sync Zotero, search papers, and capture reading cards with citation evidence.',
      href: `/projects/${projectId}/references`,
      evidence: zh ? `${counts?.papers ?? 0} 篇文献` : `${counts?.papers ?? 0} papers`,
      ready: (counts?.papers ?? 0) > 0,
    },
    {
      index: '03',
      icon: Route,
      title: zh ? '综合为科研任务' : 'Synthesize a research mission',
      description: zh ? '沿范围、文献、精读、综述、实验方案逐步推进，每一步人工确认。' : 'Move through scope, literature, reading, review, and experiment planning with approval gates.',
      href: `/projects/${projectId}/missions`,
      evidence: zh ? `${missionItems.length} 个任务 · ${activeMissions} 个进行中` : `${missionItems.length} missions · ${activeMissions} active`,
      ready: missionItems.length > 0,
    },
    {
      index: '04',
      icon: FlaskConical,
      title: zh ? '设计并复盘实验' : 'Design and review experiments',
      description: zh ? '把实验方案映射到运行、指标与日志，获得导师式下一步建议。' : 'Connect plans to runs, metrics, and logs, then receive mentor-style next actions.',
      href: `/projects/${projectId}/experiments`,
      evidence: zh ? `${counts?.experiment_plans ?? 0} 份实验方案` : `${counts?.experiment_plans ?? 0} experiment plans`,
      ready: (counts?.experiment_plans ?? 0) > 0,
    },
    {
      index: '05',
      icon: FileText,
      title: zh ? '写作、审稿与发布' : 'Write, review, and release',
      description: zh ? '论文工作区持续写作，结合实验结果模拟审稿，再生成发布资产。' : 'Draft continuously, review against real experiment results, and generate release assets.',
      href: `/projects/${projectId}/paper`,
      evidence: zh ? `${counts?.reading_notes ?? 0} 条可复用笔记` : `${counts?.reading_notes ?? 0} reusable notes`,
      ready: (counts?.reading_notes ?? 0) > 0,
    },
  ];

  return (
    <div className="-m-5 min-h-[calc(100dvh-4rem)] bg-bg lg:-m-6 xl:-m-8">
      <section className="mission-grid relative overflow-hidden border-b border-border bg-surface px-6 py-10 lg:px-10 lg:py-12">
        <div className="relative grid items-end gap-8 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="success" size="sm">RESEARCH WORKSPACE</Badge>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-faint">{project.data.status}</span>
            </div>
            <h1 className="mt-5 max-w-4xl text-4xl font-semibold tracking-[-0.055em] text-text lg:text-5xl">{project.data.name}</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted">
              {project.data.description ?? (zh ? '把零散研究材料转成可追溯的文献证据、实验设计与论文成果。' : 'Turn scattered research material into traceable evidence, experiment designs, and paper outputs.')}
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Link href={latestMission ? `/projects/${projectId}/missions/${latestMission.id}` : `/projects/${projectId}/missions`} className="inline-flex h-10 items-center gap-2 bg-accent px-4 text-sm font-semibold text-accent-fg shadow-sm hover:bg-accent-hover">
                <Sparkles className="h-4 w-4" />
                {latestMission ? (zh ? '继续最近任务' : 'Continue latest mission') : (zh ? '创建科研任务' : 'Create a research mission')}
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link href={`/projects/${projectId}/inbox`} className="inline-flex h-10 items-center gap-2 border border-border-strong bg-surface px-4 text-sm font-medium text-text hover:bg-surface-2">
                <Inbox className="h-4 w-4" />{zh ? '导入研究材料' : 'Import research material'}
              </Link>
            </div>
          </div>
          <div className="border border-border bg-overlay/90 p-5 shadow-md backdrop-blur">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-faint">{zh ? '项目实况' : 'Live project state'}</p>
            <div className="mt-4 grid grid-cols-2 gap-px bg-border">
              <Stat label={zh ? '文献' : 'Papers'} value={counts?.papers} />
              <Stat label={zh ? '科研任务' : 'Missions'} value={counts?.missions} />
              <Stat label={zh ? '实验方案' : 'Plans'} value={counts?.experiment_plans} />
              <Stat label={zh ? '阅读笔记' : 'Notes'} value={counts?.reading_notes} />
            </div>
            {latestMission ? (
              <Link href={`/projects/${projectId}/missions/${latestMission.id}`} className="mt-4 block border-l-2 border-accent pl-3 hover:bg-surface-2/40">
                <p className="text-[10px] text-faint">{zh ? '最近任务' : 'Latest mission'} · {Math.round(latestMission.progress)}%</p>
                <p className="mt-1 line-clamp-2 text-xs font-medium leading-5 text-text">{latestMission.topic}</p>
              </Link>
            ) : <p className="mt-4 text-xs leading-5 text-muted">{zh ? '尚无科研任务。先从一个明确问题开始。' : 'No research mission yet. Start from one clear question.'}</p>}
          </div>
        </div>
      </section>

      <section className="px-6 py-8 lg:px-10 lg:py-10">
        <div className="mb-6 max-w-3xl">
          <p className="text-xs font-medium text-accent">Research loop</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.035em] text-text">{zh ? '从输入到发布，一条可追溯链路' : 'One traceable path from input to release'}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{zh ? '状态只由真实项目对象计算。打开任一步即可继续工作，不使用演示进度。' : 'Every state comes from persisted project objects. Open any step to continue with no demo progress.'}</p>
        </div>
        <div className="workspace-panel overflow-hidden">
          {flow.map((step, position) => {
            const Icon = step.icon;
            return (
              <Link key={step.index} href={step.href} className="group grid min-h-24 grid-cols-[2.5rem_2.5rem_minmax(0,1fr)_1.5rem] items-center gap-4 border-b border-border px-4 py-4 last:border-b-0 hover:bg-surface-2/65 sm:grid-cols-[2.5rem_2.5rem_minmax(12rem,0.75fr)_minmax(16rem,1.25fr)_1.5rem] lg:grid-cols-[2.5rem_2.5rem_minmax(12rem,0.75fr)_minmax(16rem,1.25fr)_auto_1.5rem] sm:px-5">
                <span className="font-mono text-[11px] text-faint">{String(position + 1).padStart(2, '0')}</span>
                <span className={`grid h-9 w-9 place-items-center rounded-md ${step.ready ? 'bg-success-bg text-success' : 'bg-surface-2 text-muted'}`}>
                  {step.ready ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                </span>
                <h3 className="text-sm font-semibold tracking-[-0.01em] text-text">{step.title}</h3>
                <p className="hidden text-xs leading-5 text-muted sm:block">{step.description}</p>
                <span className="hidden whitespace-nowrap font-mono text-[10px] text-faint lg:block">{step.evidence}</span>
                <ChevronRight className="h-4 w-4 text-faint transition-transform group-hover:translate-x-1 group-hover:text-accent" />
              </Link>
            );
          })}
        </div>
      </section>

      <section className="grid gap-4 border-t border-border bg-surface-2/35 px-6 py-8 lg:grid-cols-4 lg:px-10">
        <QuickLink icon={Code2} title={zh ? 'AI IDE' : 'AI IDE'} description={zh ? '编辑本地工作区、审查 Agent 补丁并运行受限命令。' : 'Edit local files, review agent patches, and run allowlisted commands.'} href={`/projects/${projectId}/ide`} />
        <QuickLink icon={FlaskConical} title={zh ? '实验面板' : 'Experiments'} description={zh ? '查看真实运行、指标和日志。' : 'Inspect persisted runs, metrics, and logs.'} href={`/projects/${projectId}/experiments`} />
        <QuickLink icon={ShieldCheck} title={zh ? '模拟审稿' : 'Peer review'} description={zh ? '基于论文与实验上下文生成审稿意见。' : 'Review against the manuscript and experiment context.'} href={`/projects/${projectId}/reviewer`} />
        <QuickLink icon={Megaphone} title={zh ? '成果发布' : 'Release studio'} description={zh ? '准备宣传页、README 与海报资产。' : 'Prepare a project page, README, and poster assets.'} href={`/projects/${projectId}/release`} />
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | undefined }) {
  return <div className="bg-surface p-3"><p className="font-mono text-xl font-semibold text-text">{value ?? '—'}</p><p className="mt-1 text-[9px] uppercase tracking-wider text-faint">{label}</p></div>;
}

function QuickLink({ icon: Icon, title, description, href }: { icon: typeof Code2; title: string; description: string; href: string }) {
  return <Link href={href} className="group border-l border-border pl-4"><Icon className="h-4 w-4 text-accent" /><h3 className="mt-3 text-sm font-semibold text-text">{title}</h3><p className="mt-1 text-xs leading-5 text-muted">{description}</p><span className="mt-3 inline-flex items-center gap-1 text-[10px] font-medium text-success">OPEN <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-1" /></span></Link>;
}
