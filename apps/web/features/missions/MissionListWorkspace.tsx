'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowUpRight,
  CheckCircle2,
  CircleDotDashed,
  Compass,
  FileSearch,
  FlaskConical,
  History,
  Route,
  Sparkles,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  createMission,
  listMissions,
  type MissionStatus,
  type MissionSummary,
} from '@/lib/api/missions';
import { useI18n } from '@/lib/i18n';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';

const STATUS: Record<MissionStatus, { zh: string; en: string; variant: 'neutral' | 'info' | 'warn' | 'success' }> = {
  draft: { zh: '待确认', en: 'Draft', variant: 'neutral' },
  active: { zh: '进行中', en: 'Active', variant: 'info' },
  paused: { zh: '已暂停', en: 'Paused', variant: 'warn' },
  completed: { zh: '已完成', en: 'Completed', variant: 'success' },
  archived: { zh: '已归档', en: 'Archived', variant: 'neutral' },
};

const STEP_LABELS = {
  zh: {
    scope: '范围确认',
    literature: '文献与聚类',
    reading: '阅读卡',
    review: '综述',
    experiment_plan: '实验方案',
  },
  en: {
    scope: 'Scope',
    literature: 'Literature',
    reading: 'Reading cards',
    review: 'Review',
    experiment_plan: 'Experiment plan',
  },
} as const;

export function MissionListWorkspace({ projectId }: { projectId: string }) {
  const { locale } = useI18n();
  const lang = locale === 'zh-CN' ? 'zh' : 'en';
  const router = useRouter();
  const queryClient = useQueryClient();
  const [topic, setTopic] = useState('');
  const [objective, setObjective] = useState('');
  const [field, setField] = useState('');

  const missions = useQuery({
    queryKey: ['missions', projectId],
    queryFn: () => listMissions(projectId),
  });
  const create = useMutation({
    mutationFn: () =>
      createMission(projectId, {
        topic: topic.trim(),
        objective: objective.trim(),
        field: field.trim() || undefined,
        scope: { minimum_papers: 8, sources: ['arxiv', 'openalex', 'semantic_scholar'] },
      }),
    onSuccess: (mission) => {
      queryClient.invalidateQueries({ queryKey: ['missions', projectId] });
      router.push(`/projects/${projectId}/missions/${mission.id}`);
    },
  });

  const items = missions.data?.items ?? [];
  const stats = useMemo(() => {
    const active = items.filter((item) => ['draft', 'active', 'paused'].includes(item.status));
    const completed = items.filter((item) => item.status === 'completed');
    const average = items.length
      ? items.reduce((sum, item) => sum + item.progress, 0) / items.length
      : 0;
    return { active: active.length, completed: completed.length, average };
  }, [items]);

  const copy = lang === 'zh'
    ? {
        eyebrow: 'Research mission',
        title: '从一个研究主题，推进到可验证的实验方案',
        body: '每一步都保存范围、文献证据、阅读卡、综述版本和人工确认。你可以随时离开，再从同一位置继续。',
        active: '进行中的任务',
        completed: '完成任务',
        average: '平均进度',
        createTitle: '开始一次研究',
        createBody: '先定义主题和目标。系统不会在你确认范围前自动跑完整流程。',
        topic: '研究主题',
        topicPlaceholder: '例如：弱监督医学图像分割中的不确定性建模',
        objective: '希望得到什么',
        objectivePlaceholder: '形成结构化综述，并设计一组可复现实验',
        field: '研究领域（可选）',
        fieldPlaceholder: 'Medical AI / NLP / HCI',
        submit: '创建并确认范围',
        listTitle: '科研任务',
        listBody: '恢复进行中的研究，或查看已经确认的完整证据链。',
        empty: '还没有科研任务。右侧输入一个真实主题开始。',
        updated: '更新于',
        failure: '创建失败，请检查登录状态和 API 服务。',
      }
    : {
        eyebrow: 'Research mission',
        title: 'Move from a research topic to a testable experiment plan',
        body: 'Every step keeps its scope, literature evidence, reading cards, review versions, and human approvals. Leave at any time and resume at the same point.',
        active: 'Active missions',
        completed: 'Completed',
        average: 'Average progress',
        createTitle: 'Start a research mission',
        createBody: 'Define the topic and outcome first. The workflow will not run end-to-end before scope approval.',
        topic: 'Research topic',
        topicPlaceholder: 'e.g. uncertainty modelling in weakly supervised segmentation',
        objective: 'Expected outcome',
        objectivePlaceholder: 'Build a structured review and a reproducible experiment plan',
        field: 'Field (optional)',
        fieldPlaceholder: 'Medical AI / NLP / HCI',
        submit: 'Create and scope',
        listTitle: 'Research missions',
        listBody: 'Resume active work or inspect a completed evidence chain.',
        empty: 'No research missions yet. Start with a real topic on the right.',
        updated: 'Updated',
        failure: 'Could not create the mission. Check your session and API service.',
      };

  return (
    <div className="-m-6 min-h-[calc(100dvh-3.5rem)] bg-bg">
      <section className="mission-grid relative overflow-hidden border-b border-border bg-surface px-6 pb-8 pt-10 lg:px-10">
        <div className="relative z-10 max-w-4xl">
          <div className="mb-5 flex items-center gap-2 text-xs font-semibold tracking-[0.16em] text-muted">
            <Route className="h-4 w-4 text-info" aria-hidden="true" />
            {copy.eyebrow.toUpperCase()}
          </div>
          <h1 className="max-w-3xl text-balance text-3xl font-semibold leading-[1.12] tracking-[-0.035em] text-text md:text-5xl">
            {copy.title}
          </h1>
          <p className="mt-5 max-w-2xl text-pretty text-sm leading-7 text-muted md:text-base">
            {copy.body}
          </p>
          <div className="mt-8 flex flex-wrap gap-x-8 gap-y-3 border-l-2 border-info/40 pl-5">
            <Metric label={copy.active} value={stats.active} />
            <Metric label={copy.completed} value={stats.completed} />
            <Metric label={copy.average} value={`${stats.average.toFixed(0)}%`} />
          </div>
        </div>
      </section>

      <div className="mx-auto grid max-w-[1480px] gap-8 px-6 py-8 lg:grid-cols-[minmax(0,1.45fr)_minmax(20rem,0.75fr)] lg:px-10">
        <main>
          <div className="mb-5 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold tracking-[-0.02em] text-text">{copy.listTitle}</h2>
              <p className="mt-1 max-w-xl text-sm text-muted">{copy.listBody}</p>
            </div>
            <History className="h-5 w-5 text-faint" aria-hidden="true" />
          </div>

          {missions.isLoading && (
            <div className="space-y-3">
              <Skeleton className="h-36 w-full" />
              <Skeleton className="h-36 w-full" />
            </div>
          )}
          {missions.isError && (
            <div className="border-l-2 border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
              {missions.error instanceof Error ? missions.error.message : copy.failure}
            </div>
          )}
          {!missions.isLoading && !missions.isError && items.length === 0 && (
            <div className="flex min-h-64 flex-col items-start justify-center border-y border-dashed border-border-strong py-10">
              <Compass className="mb-4 h-7 w-7 text-faint" aria-hidden="true" />
              <p className="max-w-md text-sm leading-6 text-muted">{copy.empty}</p>
            </div>
          )}
          <div className="divide-y divide-border border-y border-border">
            {items.map((mission) => (
              <MissionRow
                key={mission.id}
                mission={mission}
                lang={lang}
                updatedLabel={copy.updated}
                onOpen={() => router.push(`/projects/${projectId}/missions/${mission.id}`)}
              />
            ))}
          </div>
        </main>

        <aside>
          <div className="sticky top-6 overflow-hidden rounded-lg border border-border bg-surface shadow-elev2">
            <div className="border-b border-border bg-surface-2/70 p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-text">
                <Sparkles className="h-4 w-4 text-info" aria-hidden="true" />
                {copy.createTitle}
              </div>
              <p className="mt-2 text-xs leading-5 text-muted">{copy.createBody}</p>
            </div>
            <form
              className="space-y-4 p-5"
              onSubmit={(event) => {
                event.preventDefault();
                if (topic.trim()) create.mutate();
              }}
            >
              <div>
                <Label htmlFor="mission-topic">{copy.topic}</Label>
                <textarea
                  id="mission-topic"
                  required
                  value={topic}
                  onChange={(event) => setTopic(event.target.value)}
                  placeholder={copy.topicPlaceholder}
                  className="mt-1.5 min-h-24 w-full resize-y rounded-md border border-border-strong bg-bg px-3 py-2.5 text-sm leading-6 text-text outline-none placeholder:text-faint focus:ring-2 focus:ring-focus/60"
                />
              </div>
              <div>
                <Label htmlFor="mission-objective">{copy.objective}</Label>
                <textarea
                  id="mission-objective"
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                  placeholder={copy.objectivePlaceholder}
                  className="mt-1.5 min-h-20 w-full resize-y rounded-md border border-border-strong bg-bg px-3 py-2.5 text-sm leading-6 text-text outline-none placeholder:text-faint focus:ring-2 focus:ring-focus/60"
                />
              </div>
              <div>
                <Label htmlFor="mission-field">{copy.field}</Label>
                <Input
                  id="mission-field"
                  className="mt-1.5 bg-bg"
                  value={field}
                  onChange={(event) => setField(event.target.value)}
                  placeholder={copy.fieldPlaceholder}
                />
              </div>
              {create.isError && (
                <p role="alert" className="border-l-2 border-danger pl-3 text-xs leading-5 text-danger">
                  {create.error instanceof ApiError ? create.error.message : copy.failure}
                </p>
              )}
              <Button type="submit" className="w-full justify-between" loading={create.isPending} disabled={!topic.trim()}>
                {copy.submit}
                <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </form>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="font-mono text-xl font-semibold tabular-nums text-text">{value}</div>
      <div className="mt-0.5 text-xs text-muted">{label}</div>
    </div>
  );
}

function MissionRow({
  mission,
  lang,
  updatedLabel,
  onOpen,
}: {
  mission: MissionSummary;
  lang: 'zh' | 'en';
  updatedLabel: string;
  onOpen: () => void;
}) {
  const status = STATUS[mission.status];
  const StageIcon = mission.current_step === 'experiment_plan'
    ? FlaskConical
    : mission.current_step === 'literature'
      ? FileSearch
      : mission.status === 'completed'
        ? CheckCircle2
        : CircleDotDashed;
  return (
    <article className="group relative py-5 transition-colors hover:bg-surface-2/60">
      <button
        type="button"
        onClick={onOpen}
        data-testid="mission-row"
        data-mission-id={mission.id}
        className="w-full px-3 text-left focus-visible:ring-inset"
      >
        <div className="flex items-start gap-4">
          <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-surface-2 text-muted group-hover:text-text">
            <StageIcon className="h-4 w-4" aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-pretty text-base font-semibold tracking-[-0.015em] text-text">
                {mission.topic}
              </h3>
              <Badge variant={status.variant} size="sm" dot>{status[lang]}</Badge>
            </div>
            {mission.objective && (
              <p className="mt-1.5 line-clamp-2 max-w-3xl text-sm leading-6 text-muted">{mission.objective}</p>
            )}
            <div className="mt-4 flex items-center gap-3">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
                <div className="h-full rounded-full bg-info transition-[width] duration-300" style={{ width: `${mission.progress}%` }} />
              </div>
              <span className="w-10 text-right font-mono text-xs tabular-nums text-muted">{mission.progress.toFixed(0)}%</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-faint">
              <span>{STEP_LABELS[lang][mission.current_step]}</span>
              {mission.field && <span>{mission.field}</span>}
              <span>{updatedLabel} {new Date(mission.last_activity_at).toLocaleDateString()}</span>
            </div>
          </div>
          <ArrowUpRight className="mt-1 h-4 w-4 shrink-0 text-faint transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-text" aria-hidden="true" />
        </div>
      </button>
    </article>
  );
}
