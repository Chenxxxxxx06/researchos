'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  ArrowRight,
  BookMarked,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  FileSearch,
  FileText,
  FlaskConical,
  LockKeyhole,
  Pause,
  Play,
  Save,
  ScrollText,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  approveMissionStep,
  getMission,
  getMissionTimeline,
  updateMission,
  updateMissionStep,
  type MissionDetail,
  type MissionStep,
  type MissionStepKind,
  type MissionStepStatus,
} from '@/lib/api/missions';
import { useI18n } from '@/lib/i18n';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';

import { LiteratureStagePanel, ReadingStagePanel } from './KnowledgeStagePanels';

const STEP_META: Record<MissionStepKind, { icon: LucideIcon; zh: string; en: string }> = {
  scope: { icon: Sparkles, zh: '范围确认', en: 'Scope' },
  literature: { icon: FileSearch, zh: '文献与聚类', en: 'Literature' },
  reading: { icon: BookMarked, zh: '阅读卡', en: 'Reading cards' },
  review: { icon: ScrollText, zh: '综述', en: 'Review' },
  experiment_plan: { icon: FlaskConical, zh: '实验方案', en: 'Experiment plan' },
};

const STATUS_META: Record<MissionStepStatus, { zh: string; en: string; variant: 'neutral' | 'info' | 'warn' | 'success' }> = {
  locked: { zh: '未解锁', en: 'Locked', variant: 'neutral' },
  ready: { zh: '可开始', en: 'Ready', variant: 'info' },
  in_progress: { zh: '进行中', en: 'In progress', variant: 'info' },
  needs_review: { zh: '待确认', en: 'Needs review', variant: 'warn' },
  completed: { zh: '已确认', en: 'Approved', variant: 'success' },
};

const TOOL_HREF: Partial<Record<MissionStepKind, string>> = {
  literature: 'research',
  reading: 'research',
  experiment_plan: 'experiments',
};

export function MissionWorkspace({ projectId, missionId }: { projectId: string; missionId: string }) {
  const { locale } = useI18n();
  const lang = locale === 'zh-CN' ? 'zh' : 'en';
  const queryClient = useQueryClient();
  const missionQuery = useQuery<MissionDetail, ApiError>({
    queryKey: ['mission', projectId, missionId],
    queryFn: () => getMission(projectId, missionId),
    retry: false,
  });
  const timeline = useQuery({
    queryKey: ['mission-timeline', projectId, missionId],
    queryFn: () => getMissionTimeline(projectId, missionId),
    retry: false,
  });

  const mission = missionQuery.data;
  const current = mission?.steps.find((step) => step.step_kind === mission.current_step) ?? null;
  const [objective, setObjective] = useState('');
  const [field, setField] = useState('');
  const [keywords, setKeywords] = useState('');
  const [yearFrom, setYearFrom] = useState('2021');
  const [yearTo, setYearTo] = useState(String(new Date().getFullYear()));
  const [minimumPapers, setMinimumPapers] = useState('8');
  const [stageNote, setStageNote] = useState('');

  useEffect(() => {
    if (!mission || !current) return;
    setObjective(mission.objective);
    setField(mission.field ?? '');
    const scope = mission.scope_json;
    const years = Array.isArray(scope.years) ? scope.years : [];
    setYearFrom(String(years[0] ?? 2021));
    setYearTo(String(years[1] ?? new Date().getFullYear()));
    setMinimumPapers(String(scope.minimum_papers ?? 8));
    setKeywords(Array.isArray(scope.keywords) ? scope.keywords.join('\n') : '');
    setStageNote(typeof current.output_json.summary === 'string' ? current.output_json.summary : '');
  }, [mission, current]);

  const refreshTimeline = () => queryClient.invalidateQueries({ queryKey: ['mission-timeline', projectId, missionId] });
  const acceptMission = (data: MissionDetail) => {
    queryClient.setQueryData(['mission', projectId, missionId], data);
    queryClient.invalidateQueries({ queryKey: ['missions', projectId] });
    refreshTimeline();
  };

  const save = useMutation({
    mutationFn: async () => {
      if (!mission || !current) throw new Error('Mission is not loaded.');
      if (current.step_kind === 'scope') {
        return updateMission(projectId, missionId, {
          expected_version: mission.version,
          objective,
          field,
          scope: {
            ...mission.scope_json,
            keywords: keywords.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean),
            years: [Number(yearFrom), Number(yearTo)],
            minimum_papers: Number(minimumPapers),
          },
        });
      }
      return updateMissionStep(projectId, missionId, current.step_kind, {
        expected_version: current.version,
        output: { ...current.output_json, summary: stageNote.trim() },
        status: 'needs_review',
      });
    },
    onSuccess: (data) => {
      acceptMission(data);
      toast({ title: lang === 'zh' ? '阶段内容已保存' : 'Step saved', variant: 'success' });
    },
    onError: (error) => handleMutationError(error, missionQuery.refetch, lang),
  });

  const start = useMutation({
    mutationFn: () => {
      if (!current) throw new Error('Mission step is not loaded.');
      return updateMissionStep(projectId, missionId, current.step_kind, {
        expected_version: current.version,
        status: 'in_progress',
      });
    },
    onSuccess: acceptMission,
    onError: (error) => handleMutationError(error, missionQuery.refetch, lang),
  });

  const approve = useMutation({
    mutationFn: () => {
      if (!current) throw new Error('Mission step is not loaded.');
      return approveMissionStep(projectId, missionId, current.step_kind, {
        expected_version: current.version,
        note: lang === 'zh' ? '用户在科研任务工作台确认' : 'Approved in Mission Workspace',
      });
    },
    onSuccess: (data) => {
      acceptMission(data);
      toast({
        title: data.status === 'completed'
          ? (lang === 'zh' ? '科研任务已完成' : 'Mission completed')
          : (lang === 'zh' ? '本阶段已确认，下一阶段已解锁' : 'Step approved; next step unlocked'),
        variant: 'success',
      });
    },
    onError: (error) => handleMutationError(error, missionQuery.refetch, lang),
  });

  const togglePause = useMutation({
    mutationFn: () => {
      if (!mission) throw new Error('Mission is not loaded.');
      return updateMission(projectId, missionId, {
        expected_version: mission.version,
        status: mission.status === 'paused' ? 'active' : 'paused',
      });
    },
    onSuccess: acceptMission,
    onError: (error) => handleMutationError(error, missionQuery.refetch, lang),
  });

  if (missionQuery.isLoading) {
    return (
      <div className="-m-6 space-y-5 p-8">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-16 w-full" />
        <div className="grid gap-5 lg:grid-cols-[1fr_22rem]"><Skeleton className="h-96" /><Skeleton className="h-96" /></div>
      </div>
    );
  }
  if (missionQuery.isError || !mission || !current) {
    return (
      <div className="mx-auto max-w-3xl py-20">
        <Link href={`/projects/${projectId}/missions`} className="mb-5 inline-flex items-center gap-1 text-sm text-muted hover:text-text">
          <ArrowLeft className="h-4 w-4" /> {lang === 'zh' ? '返回科研任务' : 'Back to missions'}
        </Link>
        <div className="border-l-2 border-danger bg-danger-bg p-5 text-sm text-danger">
          {missionQuery.error?.message ?? (lang === 'zh' ? '无法加载该科研任务。' : 'Could not load this mission.')}
        </div>
      </div>
    );
  }

  const currentMeta = STEP_META[current.step_kind];
  const CurrentIcon = currentMeta.icon;
  const toolSegment = current.step_kind === 'review'
    ? `missions/${missionId}/review`
    : current.step_kind === 'experiment_plan'
      ? `missions/${missionId}/experiment-plan`
      : TOOL_HREF[current.step_kind];
  const copy = workspaceCopy(lang, current.step_kind);

  return (
    <div className="-m-6 min-h-[calc(100dvh-3.5rem)] bg-bg">
      <header className="border-b border-border bg-surface px-6 pb-6 pt-5 lg:px-8">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0 flex-1">
            <Link href={`/projects/${projectId}/missions`} className="mb-4 inline-flex items-center gap-1.5 text-xs font-medium text-muted hover:text-text">
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              {lang === 'zh' ? '全部科研任务' : 'All missions'}
            </Link>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={mission.status === 'completed' ? 'success' : mission.status === 'paused' ? 'warn' : 'info'} dot>
                {missionStatusLabel(mission.status, lang)}
              </Badge>
              {mission.field && <span className="text-xs text-faint">{mission.field}</span>}
              <span className="font-mono text-xs tabular-nums text-faint">v{mission.version}</span>
            </div>
            <h1 className="mt-3 max-w-4xl text-balance text-2xl font-semibold leading-tight tracking-[-0.03em] text-text lg:text-3xl">
              {mission.topic}
            </h1>
            {mission.objective && <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{mission.objective}</p>}
          </div>
          {mission.status !== 'completed' && mission.status !== 'archived' && (
            <Button variant="outline" size="sm" onClick={() => togglePause.mutate()} loading={togglePause.isPending}>
              {mission.status === 'paused' ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
              {mission.status === 'paused'
                ? (lang === 'zh' ? '继续任务' : 'Resume')
                : (lang === 'zh' ? '暂停' : 'Pause')}
            </Button>
          )}
        </div>

        <div className="mt-6 flex items-center gap-3">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
            <div className="h-full rounded-full bg-info transition-[width] duration-500" style={{ width: `${mission.progress}%` }} />
          </div>
          <span className="font-mono text-xs tabular-nums text-muted">{mission.progress.toFixed(0)}%</span>
        </div>
      </header>

      <StepRoadmap mission={mission} lang={lang} />

      <div className="mx-auto grid max-w-[1540px] gap-6 px-6 py-7 lg:grid-cols-[minmax(0,1fr)_22rem] lg:px-8">
        <main className="min-w-0">
          <section className="overflow-hidden rounded-lg border border-border bg-surface shadow-elev1">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border bg-surface-2/55 p-5">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-bg text-info shadow-elev1">
                  <CurrentIcon className="h-4 w-4" aria-hidden="true" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold tracking-[-0.02em] text-text">{currentMeta[lang]}</h2>
                    <Badge variant={STATUS_META[current.status].variant} size="sm" dot>{STATUS_META[current.status][lang]}</Badge>
                  </div>
                  <p className="mt-1 max-w-2xl text-xs leading-5 text-muted">{copy.description}</p>
                </div>
              </div>
              <span className="font-mono text-[11px] text-faint">step v{current.version}</span>
            </div>

            <div className="p-5 md:p-6">
              {current.step_kind === 'scope' ? (
                <ScopeEditor
                  objective={objective}
                  field={field}
                  keywords={keywords}
                  yearFrom={yearFrom}
                  yearTo={yearTo}
                  minimumPapers={minimumPapers}
                  lang={lang}
                  onObjective={setObjective}
                  onField={setField}
                  onKeywords={setKeywords}
                  onYearFrom={setYearFrom}
                  onYearTo={setYearTo}
                  onMinimumPapers={setMinimumPapers}
                />
              ) : current.step_kind === 'literature' ? (
                <LiteratureStagePanel projectId={projectId} missionId={missionId} lang={lang} />
              ) : current.step_kind === 'reading' ? (
                <ReadingStagePanel projectId={projectId} missionId={missionId} lang={lang} />
              ) : (
                <StageEditor
                  copy={copy}
                  note={stageNote}
                  onNote={setStageNote}
                  projectId={projectId}
                  missionId={missionId}
                  toolSegment={toolSegment}
                  lang={lang}
                />
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-2/35 px-5 py-4">
              <p className="text-xs text-muted">
                {current.status === 'completed'
                  ? (lang === 'zh' ? '本阶段已人工确认，内容已锁定。' : 'This step is approved and locked.')
                  : (lang === 'zh' ? '保存不会解锁下一步；只有“确认并继续”会推进流程。' : 'Saving does not unlock the next step. Approval advances the workflow.')}
              </p>
              <div className="flex gap-2">
                {current.status === 'ready' && current.step_kind !== 'scope' && (
                  <Button variant="secondary" onClick={() => start.mutate()} loading={start.isPending}>
                    <Play className="h-3.5 w-3.5" /> {lang === 'zh' ? '开始本阶段' : 'Start step'}
                  </Button>
                )}
                {current.status !== 'completed' && (
                  <>
                    {!['literature', 'reading'].includes(current.step_kind) && (
                      <Button variant="secondary" onClick={() => save.mutate()} loading={save.isPending}>
                        <Save className="h-3.5 w-3.5" /> {lang === 'zh' ? '保存' : 'Save'}
                      </Button>
                    )}
                    <Button onClick={() => approve.mutate()} loading={approve.isPending}>
                      <Check className="h-3.5 w-3.5" /> {lang === 'zh' ? '确认并继续' : 'Approve and continue'}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </>
                )}
              </div>
            </div>
          </section>
        </main>

        <aside className="space-y-5">
          <section className="rounded-lg border border-border bg-surface p-4 shadow-elev1">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-text">{lang === 'zh' ? '任务时间线' : 'Mission timeline'}</h2>
              <Clock3 className="h-4 w-4 text-faint" aria-hidden="true" />
            </div>
            {timeline.isLoading && <Skeleton className="mt-4 h-40 w-full" />}
            <ol className="mt-4 space-y-4">
              {(timeline.data?.items ?? []).slice(0, 12).map((event, index) => (
                <li key={event.id} className="relative flex gap-3">
                  {index < Math.min((timeline.data?.items.length ?? 0) - 1, 11) && <span className="absolute left-[5px] top-3 h-[calc(100%+0.5rem)] w-px bg-border" />}
                  <span className="relative mt-1 h-2.5 w-2.5 shrink-0 rounded-full border-2 border-surface bg-info" />
                  <div className="min-w-0">
                    <p className="text-xs leading-5 text-text">{event.summary}</p>
                    <p className="mt-0.5 font-mono text-[10px] text-faint">{new Date(event.created_at).toLocaleString()}</p>
                  </div>
                </li>
              ))}
            </ol>
            {!timeline.isLoading && (timeline.data?.items.length ?? 0) === 0 && (
              <p className="mt-4 text-xs text-muted">{lang === 'zh' ? '暂无历史记录。' : 'No timeline events yet.'}</p>
            )}
          </section>

          <section className="border-l-2 border-info/45 bg-info-bg/55 p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-info">
              <FileText className="h-3.5 w-3.5" /> {lang === 'zh' ? '证据规则' : 'Evidence rule'}
            </div>
            <p className="mt-2 text-xs leading-5 text-muted">
              {lang === 'zh'
                ? '后续生成的阅读卡、综述和实验方案会保留论文片段、人工修改与 Agent Run 版本。没有来源的内容必须标记为待证据。'
                : 'Reading cards, review sections, and experiment plans will retain their paper evidence, human edits, and Agent Run versions. Unsupported content must remain marked as needing evidence.'}
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}

function StepRoadmap({ mission, lang }: { mission: MissionDetail; lang: 'zh' | 'en' }) {
  return (
    <nav aria-label={lang === 'zh' ? '科研任务步骤' : 'Mission steps'} className="overflow-x-auto border-b border-border bg-surface/75 px-6 py-4 lg:px-8">
      <ol className="mx-auto flex min-w-[760px] max-w-[1300px] items-center">
        {mission.steps.map((step, index) => {
          const meta = STEP_META[step.step_kind];
          const Icon = step.status === 'completed' ? CheckCircle2 : step.status === 'locked' ? LockKeyhole : meta.icon;
          const active = mission.current_step === step.step_kind;
          return (
            <li key={step.id} className="flex flex-1 items-center">
              <div className="flex min-w-0 items-center gap-2.5">
                <span className={cn(
                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-md border text-xs transition-colors',
                  step.status === 'completed' && 'border-success/30 bg-success-bg text-success',
                  active && step.status !== 'completed' && 'border-info/35 bg-info-bg text-info',
                  !active && step.status !== 'completed' && 'border-border bg-surface-2 text-faint',
                )}>
                  <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <p className={cn('truncate text-xs font-medium', active ? 'text-text' : 'text-muted')}>{meta[lang]}</p>
                  <p className="truncate text-[10px] text-faint">{STATUS_META[step.status][lang]}</p>
                </div>
              </div>
              {index < mission.steps.length - 1 && <div className={cn('mx-3 h-px flex-1', step.status === 'completed' ? 'bg-success/40' : 'bg-border')} />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function ScopeEditor(props: {
  objective: string;
  field: string;
  keywords: string;
  yearFrom: string;
  yearTo: string;
  minimumPapers: string;
  lang: 'zh' | 'en';
  onObjective: (value: string) => void;
  onField: (value: string) => void;
  onKeywords: (value: string) => void;
  onYearFrom: (value: string) => void;
  onYearTo: (value: string) => void;
  onMinimumPapers: (value: string) => void;
}) {
  const zh = props.lang === 'zh';
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <div className="md:col-span-2">
        <Label htmlFor="mission-objective">{zh ? '研究目标与预期产物' : 'Objective and expected output'}</Label>
        <textarea id="mission-objective" value={props.objective} onChange={(event) => props.onObjective(event.target.value)} className="mt-1.5 min-h-24 w-full resize-y rounded-md border border-border-strong bg-bg p-3 text-sm leading-6 text-text outline-none focus:ring-2 focus:ring-focus/60" placeholder={zh ? '例如：形成结构化综述，识别研究空白，并设计可复现实验。' : 'Build a structured review, identify the gap, and design a reproducible experiment.'} />
      </div>
      <div>
        <Label htmlFor="mission-field">{zh ? '研究领域' : 'Research field'}</Label>
        <Input id="mission-field" className="mt-1.5 bg-bg" value={props.field} onChange={(event) => props.onField(event.target.value)} placeholder="Medical AI / NLP / HCI" />
      </div>
      <div>
        <Label htmlFor="mission-min-papers">{zh ? '最低纳入论文数' : 'Minimum included papers'}</Label>
        <Input id="mission-min-papers" type="number" min={1} max={200} className="mt-1.5 bg-bg font-mono tabular-nums" value={props.minimumPapers} onChange={(event) => props.onMinimumPapers(event.target.value)} />
      </div>
      <div className="md:col-span-2">
        <Label htmlFor="mission-keywords">{zh ? '检索关键词（每行一个）' : 'Search terms (one per line)'}</Label>
        <textarea id="mission-keywords" value={props.keywords} onChange={(event) => props.onKeywords(event.target.value)} className="mt-1.5 min-h-28 w-full resize-y rounded-md border border-border-strong bg-bg p-3 font-mono text-xs leading-6 text-text outline-none focus:ring-2 focus:ring-focus/60" placeholder={'weak supervision\nuncertainty estimation\nmedical image segmentation'} />
      </div>
      <div>
        <Label htmlFor="mission-year-from">{zh ? '起始年份' : 'From year'}</Label>
        <Input id="mission-year-from" type="number" className="mt-1.5 bg-bg font-mono tabular-nums" value={props.yearFrom} onChange={(event) => props.onYearFrom(event.target.value)} />
      </div>
      <div>
        <Label htmlFor="mission-year-to">{zh ? '结束年份' : 'To year'}</Label>
        <Input id="mission-year-to" type="number" className="mt-1.5 bg-bg font-mono tabular-nums" value={props.yearTo} onChange={(event) => props.onYearTo(event.target.value)} />
      </div>
    </div>
  );
}

function StageEditor({
  copy,
  note,
  onNote,
  projectId,
  missionId,
  toolSegment,
  lang,
}: {
  copy: ReturnType<typeof workspaceCopy>;
  note: string;
  onNote: (value: string) => void;
  projectId: string;
  missionId: string;
  toolSegment?: string;
  lang: 'zh' | 'en';
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_17rem]">
      <div>
        <Label htmlFor="mission-stage-note">{copy.noteLabel}</Label>
        <textarea id="mission-stage-note" value={note} onChange={(event) => onNote(event.target.value)} className="mt-1.5 min-h-52 w-full resize-y rounded-md border border-border-strong bg-bg p-3 text-sm leading-6 text-text outline-none focus:ring-2 focus:ring-focus/60" placeholder={copy.notePlaceholder} />
      </div>
      <div className="space-y-4">
        <div className="bg-surface-2 p-4">
          <h3 className="text-xs font-semibold text-text">{copy.checkTitle}</h3>
          <ul className="mt-3 space-y-2.5 text-xs leading-5 text-muted">
            {copy.checks.map((item) => <li key={item} className="flex gap-2"><Circle className="mt-1 h-2.5 w-2.5 shrink-0 text-faint" />{item}</li>)}
          </ul>
        </div>
        {toolSegment && (
          <Link href={`/projects/${projectId}/${toolSegment}?mission=${missionId}`} className="flex items-center justify-between rounded-md border border-border-strong bg-surface px-3 py-2.5 text-xs font-medium text-text hover:bg-surface-2">
            {copy.openTool}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        )}
        <p className="text-[11px] leading-5 text-faint">
          {lang === 'zh' ? '本阶段后续会接入结构化产物编辑器；当前摘要已真实保存到 MissionStep，不是浏览器占位。' : 'A structured editor will replace this brief in the next increment. The current summary is already persisted in MissionStep.'}
        </p>
      </div>
    </div>
  );
}

function workspaceCopy(lang: 'zh' | 'en', step: MissionStepKind) {
  const zh = {
    scope: { description: '确认问题范围、检索词、时间和最低证据数量。', noteLabel: '', notePlaceholder: '', checkTitle: '', checks: [], openTool: '' },
    literature: { description: '检索并纳入论文，确认全文解析状态，随后形成可调整的主题聚类。', noteLabel: '本阶段产物摘要', notePlaceholder: '记录已纳入论文、主要主题和仍需补充的证据。', checkTitle: '完成前检查', checks: ['至少纳入 5 篇相关论文', '核心论文完成全文或摘要解析', '聚类结果经过人工确认'], openTool: '打开 Research Copilot' },
    reading: { description: '为核心论文生成并确认结构化阅读卡，将问题、方法、结论和复现要点绑定到证据。', noteLabel: '本阶段产物摘要', notePlaceholder: '记录已确认阅读卡、关键方法差异和待核实问题。', checkTitle: '完成前检查', checks: ['核心论文均有阅读卡', '主要结论绑定原文证据', 'AI 推断与作者陈述分开'], openTool: '打开论文库与阅读室' },
    review: { description: '基于确认的聚类、阅读卡和笔记形成综述大纲，并按章节生成带引用草稿。', noteLabel: '本阶段产物摘要', notePlaceholder: '记录大纲结构、已完成章节和缺少来源的主张。', checkTitle: '完成前检查', checks: ['大纲不是逐篇罗列', '每个章节绑定论文集合', '无来源事实保持待证据状态'], openTool: '打开论文工作区' },
    experiment_plan: { description: '把研究空白变成可证伪问题，明确变量、对照、数据、指标、预算和决策规则。', noteLabel: '本阶段产物摘要', notePlaceholder: '记录假设、实验组、变量、指标和尚未解决的执行风险。', checkTitle: '完成前检查', checks: ['自变量/因变量/控制变量明确', 'baseline 有文献或待验证标记', '决策规则和停止条件可执行'], openTool: '打开实验面板' },
  } as const;
  const en = {
    scope: { description: 'Confirm the question boundary, search terms, time range, and evidence target.', noteLabel: '', notePlaceholder: '', checkTitle: '', checks: [], openTool: '' },
    literature: { description: 'Search and include papers, confirm ingestion status, then build a reviewable topic clustering.', noteLabel: 'Step output brief', notePlaceholder: 'Record included papers, main themes, and missing evidence.', checkTitle: 'Before approval', checks: ['Include at least five relevant papers', 'Ingest core papers or record abstract-only status', 'Review the topic clusters'], openTool: 'Open Research Copilot' },
    reading: { description: 'Generate and approve structured reading cards grounded in paper evidence.', noteLabel: 'Step output brief', notePlaceholder: 'Record approved cards, method differences, and open questions.', checkTitle: 'Before approval', checks: ['Core papers have reading cards', 'Main claims link to source evidence', 'Separate inference from author statements'], openTool: 'Open library and reading room' },
    review: { description: 'Turn approved clusters, cards, and notes into an outline and cited section drafts.', noteLabel: 'Step output brief', notePlaceholder: 'Record the outline, completed sections, and unsupported claims.', checkTitle: 'Before approval', checks: ['Outline synthesizes themes', 'Each section has a paper set', 'Unsupported facts remain marked'], openTool: 'Open Paper Workspace' },
    experiment_plan: { description: 'Convert the research gap into a falsifiable design with variables, controls, metrics, budget, and decision rules.', noteLabel: 'Step output brief', notePlaceholder: 'Record hypotheses, groups, variables, metrics, and execution risks.', checkTitle: 'Before approval', checks: ['Independent, dependent, and control variables are explicit', 'Baselines have evidence or a verification flag', 'Decision and stop rules are executable'], openTool: 'Open Experiments' },
  } as const;
  return (lang === 'zh' ? zh : en)[step];
}

function missionStatusLabel(status: MissionDetail['status'], lang: 'zh' | 'en') {
  const labels = {
    draft: { zh: '待确认', en: 'Draft' },
    active: { zh: '进行中', en: 'Active' },
    paused: { zh: '已暂停', en: 'Paused' },
    completed: { zh: '已完成', en: 'Completed' },
    archived: { zh: '已归档', en: 'Archived' },
  } as const;
  return labels[status][lang];
}

function handleMutationError(error: unknown, refetch: () => unknown, lang: 'zh' | 'en') {
  if (error instanceof ApiError && (error.code === 'mission_version_conflict' || error.code === 'mission_step_version_conflict')) {
    toast({
      title: lang === 'zh' ? '内容已被其他操作更新' : 'This content changed elsewhere',
      description: lang === 'zh' ? '页面将刷新到最新版本，请检查后重新提交。' : 'The latest version will be loaded. Review it before submitting again.',
      variant: 'warning',
    });
    void refetch();
    return;
  }
  toast({
    title: lang === 'zh' ? '操作失败' : 'Action failed',
    description: error instanceof Error ? error.message : undefined,
    variant: 'error',
  });
}
