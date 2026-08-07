'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowLeft,
  Beaker,
  Check,
  Database,
  FlaskConical,
  Gauge,
  History,
  Plus,
  Rocket,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
  Variable,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';
import { getAgentRun } from '@/lib/api/agents';
import { ApiError } from '@/lib/api/client';
import {
  generateExperimentPlan,
  getExperimentPlan,
  listExperimentPlanVersions,
  publishExperimentPlan,
  saveExperimentPlan,
  type ExperimentPlan,
  type ExperimentPlanInput,
  type PlanBaseline,
  type PlanDataset,
  type PlanMatrixRow,
  type PlanMetric,
  type PlanRisk,
  type PlanVariable,
} from '@/lib/api/experimentPlans';
import { listMissionPapers } from '@/lib/api/knowledge';
import { useI18n } from '@/lib/i18n';

const blank: ExperimentPlanInput = {
  title: '',
  research_gap: '',
  hypothesis: '',
  variables: [],
  baselines: [],
  datasets: [],
  metrics: [],
  matrix: [],
  decision_rules: [],
  stop_conditions: [],
  risks: [],
  reproducibility: [],
  status: 'draft',
};

function toInput(plan: ExperimentPlan): ExperimentPlanInput {
  return {
    expected_version: plan.version,
    title: plan.title,
    research_gap: plan.research_gap,
    hypothesis: plan.hypothesis,
    variables: plan.variables_json,
    baselines: plan.baselines_json,
    datasets: plan.datasets_json,
    metrics: plan.metrics_json,
    matrix: plan.matrix_json,
    decision_rules: plan.decision_rules_json,
    stop_conditions: plan.stop_conditions_json,
    risks: plan.risks_json,
    reproducibility: plan.reproducibility_json,
    status: plan.status === 'published' ? 'approved' : plan.status,
  };
}

export function ExperimentPlanWorkspace({ projectId, missionId }: { projectId: string; missionId: string }) {
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const queryClient = useQueryClient();
  const plan = useQuery({ queryKey: ['experiment-plan', projectId, missionId], queryFn: () => getExperimentPlan(projectId, missionId), retry: false });
  const papers = useQuery({ queryKey: ['mission-papers', projectId, missionId], queryFn: () => listMissionPapers(projectId, missionId) });
  const versions = useQuery({ queryKey: ['experiment-plan-versions', projectId, missionId], queryFn: () => listExperimentPlanVersions(projectId, missionId), enabled: Boolean(plan.data) });
  const [draft, setDraft] = useState<ExperimentPlanInput>(blank);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  useEffect(() => {
    if (plan.data) setDraft(toInput(plan.data));
  }, [plan.data]);

  const issues = useMemo(() => readinessIssues(draft, zh), [draft, zh]);
  const grounded = draft.baselines.filter((item) => item.evidence_status === 'grounded').length;
  const save = useMutation({
    mutationFn: (status: ExperimentPlanInput['status']) => saveExperimentPlan(projectId, missionId, { ...draft, status }),
    onSuccess: (data) => {
      queryClient.setQueryData(['experiment-plan', projectId, missionId], data);
      void queryClient.invalidateQueries({ queryKey: ['experiment-plan-versions', projectId, missionId] });
      toast({ title: zh ? '实验方案与新版本已保存' : 'Experiment plan and version saved' });
    },
    onError: (error) => toast({ title: zh ? '方案保存失败' : 'Could not save plan', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const generate = useMutation({
    mutationFn: () => generateExperimentPlan(projectId, missionId, plan.data?.version ?? 0, Boolean(plan.data)),
    onSuccess: (run) => {
      setActiveRunId(run.agent_run_id);
      toast({ title: zh ? '实验规划 Agent 已启动' : 'Experiment planner started', description: zh ? '正在从综述主张与原文证据推导变量、基线和实验矩阵。' : 'Deriving variables, baselines, and a matrix from review evidence.' });
    },
    onError: (error) => toast({ title: zh ? '无法启动实验规划 Agent' : 'Could not start planner', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const publish = useMutation({
    mutationFn: () => publishExperimentPlan(projectId, missionId),
    onSuccess: ({ plan: data }) => {
      queryClient.setQueryData(['experiment-plan', projectId, missionId], data);
      toast({ title: zh ? '已发布到实验面板' : 'Published to Experiments', description: zh ? '实验名称、目标、指标方向与默认矩阵已写入可运行实验。' : 'Name, goal, metric directions, and matrix are now available to experiment runs.' });
    },
    onError: (error) => toast({ title: zh ? '尚不能发布' : 'Plan is not publishable', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const activeRun = useQuery({
    queryKey: ['agent-run', projectId, activeRunId],
    queryFn: () => getAgentRun(projectId, activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1200 : false,
  });
  useEffect(() => {
    if (!activeRunId || !activeRun.data) return;
    if (activeRun.data.status === 'completed') {
      void queryClient.invalidateQueries({ queryKey: ['experiment-plan', projectId, missionId] });
      void queryClient.invalidateQueries({ queryKey: ['experiment-plan-versions', projectId, missionId] });
      void queryClient.invalidateQueries({ queryKey: ['mission-timeline', projectId, missionId] });
      toast({ title: zh ? '结构化实验方案已生成，等待人工复核' : 'Structured plan generated for review' });
      setActiveRunId(null);
    } else if (['failed', 'cancelled'].includes(activeRun.data.status)) {
      toast({ title: zh ? '实验规划 Agent 未完成' : 'Planner did not complete', description: activeRun.data.error_json?.message, variant: 'error' });
      setActiveRunId(null);
    }
  }, [activeRun.data, activeRunId, missionId, projectId, queryClient, zh]);

  if (plan.isLoading) return <div className="p-8"><Skeleton className="h-[36rem] w-full" /></div>;
  const missing = plan.error instanceof ApiError && plan.error.status === 404;
  if (plan.error && !missing) return <div className="p-8 text-sm text-danger">{plan.error.message}</div>;

  return <div className="-m-6 min-h-[calc(100dvh-3.5rem)] bg-bg">
    <header className="mission-grid border-b border-border bg-surface px-7 pb-7 pt-6">
      <Link href={`/projects/${projectId}/missions/${missionId}`} className="inline-flex items-center gap-1 text-xs text-muted hover:text-text"><ArrowLeft className="h-3.5 w-3.5" />{zh ? '返回科研任务' : 'Back to mission'}</Link>
      <div className="mt-5 flex flex-wrap items-end justify-between gap-5"><div><div className="flex items-center gap-2"><Badge variant="accent" size="sm">EXPERIMENT PLAN {plan.data ? `v${plan.data.version}` : 'NEW'}</Badge>{plan.data && <span className="text-[10px] text-faint">{plan.data.status}</span>}</div><h1 className="mt-3 text-3xl font-semibold tracking-[-0.035em] text-text">{zh ? '把研究空白变成可证伪的实验' : 'Turn the research gap into a falsifiable experiment'}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{zh ? '这里的字段会直接发布为实验配置；基线证据、变量角色和停止条件均参与发布门禁。' : 'These fields publish directly into experiment configuration; evidence, variable roles, and stop rules are release gates.'}</p></div><div className="flex gap-2"><Link href={`/projects/${projectId}/missions/${missionId}/data-query`} className="inline-flex h-9 items-center gap-2 rounded-md border border-border-strong bg-surface px-3 text-xs font-medium text-text hover:bg-surface-2"><Database className="h-3.5 w-3.5" />{zh ? 'SQL 数据分析' : 'SQL Data Lab'}</Link><Button variant="secondary" onClick={() => generate.mutate()} loading={generate.isPending || Boolean(activeRunId)}><Sparkles className="h-3.5 w-3.5" />{plan.data ? (zh ? '按当前综述重生成' : 'Regenerate from review') : (zh ? 'Agent 生成方案' : 'Generate plan')}</Button><Button onClick={() => publish.mutate()} loading={publish.isPending} disabled={!plan.data || issues.length > 0 || plan.data.status === 'published'}><Rocket className="h-3.5 w-3.5" />{plan.data?.status === 'published' ? (zh ? '已发布' : 'Published') : (zh ? '发布到实验面板' : 'Publish to Experiments')}</Button></div></div>
      {activeRunId && <div className="mt-5 border-l-2 border-accent bg-accent-soft px-4 py-2 text-xs text-text">{zh ? `实验规划 Agent：${activeRun.data?.status ?? 'queued'}，完成后自动刷新。` : `Experiment planner: ${activeRun.data?.status ?? 'queued'}; this page refreshes on completion.`}</div>}
      <div className="mt-6 flex flex-wrap gap-8 border-l-2 border-accent/50 pl-5"><Metric label={zh ? '变量' : 'Variables'} value={draft.variables.length} /><Metric label={zh ? '基线证据' : 'Grounded baselines'} value={`${grounded}/${draft.baselines.length}`} /><Metric label={zh ? '实验单元' : 'Matrix cells'} value={draft.matrix.length} /><Metric label={zh ? '发布阻断项' : 'Release blockers'} value={issues.length} /></div>
    </header>
    <div className="grid lg:grid-cols-[minmax(0,1fr)_20rem]">
      <main className="space-y-8 p-6 lg:p-8">
        <section className="grid gap-5 xl:grid-cols-2"><Field label={zh ? '方案标题' : 'Plan title'} value={draft.title} onChange={(title) => setDraft({ ...draft, title })} /><Area label={zh ? '研究空白' : 'Research gap'} value={draft.research_gap} onChange={(research_gap) => setDraft({ ...draft, research_gap })} rows={5} /><Area label={zh ? '可证伪假设' : 'Falsifiable hypothesis'} value={draft.hypothesis} onChange={(hypothesis) => setDraft({ ...draft, hypothesis })} rows={5} wide /></section>
        <EditorSection icon={Variable} title={zh ? '变量设计' : 'Variable design'} subtitle={zh ? '自变量、因变量、控制变量缺一不可' : 'Independent, dependent, and control variables are required'} onAdd={() => setDraft({ ...draft, variables: [...draft.variables, { name: '', role: 'independent', operational_definition: '', levels_or_measurement: '' }] })}><div className="space-y-2">{draft.variables.map((item, index) => <VariableRow key={index} item={item} onChange={(value) => setDraft({ ...draft, variables: replace(draft.variables, index, value) })} onRemove={() => setDraft({ ...draft, variables: remove(draft.variables, index) })} />)}</div></EditorSection>
        <EditorSection icon={ShieldCheck} title={zh ? '对照基线与文献证据' : 'Baselines and literature evidence'} subtitle={zh ? 'Agent 可把基线绑定到论文原文；人工新增项默认待补证据' : 'The agent binds baselines to source text; manual rows start unresolved'} onAdd={() => setDraft({ ...draft, baselines: [...draft.baselines, { name: '', rationale: '', source_paper_id: null, evidence_section_id: null, evidence_quote: '', evidence_status: 'needs_evidence' }] })}><div className="space-y-3">{draft.baselines.map((item, index) => <BaselineRow key={index} item={item} papers={papers.data ?? []} zh={zh} onChange={(value) => setDraft({ ...draft, baselines: replace(draft.baselines, index, value) })} onRemove={() => setDraft({ ...draft, baselines: remove(draft.baselines, index) })} />)}</div></EditorSection>
        <div className="grid gap-8 xl:grid-cols-2"><EditorSection icon={Beaker} title={zh ? '数据与切分' : 'Data and splits'} onAdd={() => setDraft({ ...draft, datasets: [...draft.datasets, { name: '', split: '', preprocessing: '', license_or_access: '' }] })}>{draft.datasets.map((item, index) => <DatasetRow key={index} item={item} onChange={(value) => setDraft({ ...draft, datasets: replace(draft.datasets, index, value) })} onRemove={() => setDraft({ ...draft, datasets: remove(draft.datasets, index) })} />)}</EditorSection><EditorSection icon={Gauge} title={zh ? '评价指标' : 'Metrics'} onAdd={() => setDraft({ ...draft, metrics: [...draft.metrics, { name: '', direction: 'max', primary: draft.metrics.length === 0, unit: '' }] })}>{draft.metrics.map((item, index) => <MetricRow key={index} item={item} onChange={(value) => setDraft({ ...draft, metrics: replace(draft.metrics, index, value) })} onRemove={() => setDraft({ ...draft, metrics: remove(draft.metrics, index) })} />)}</EditorSection></div>
        <EditorSection icon={FlaskConical} title={zh ? '实验矩阵' : 'Experiment matrix'} subtitle={zh ? '每行对应一组可执行比较；因素配置会写入默认实验配置' : 'Each row is an executable comparison stored in the default config'} onAdd={() => setDraft({ ...draft, matrix: [...draft.matrix, { name: '', factors: { method: ['baseline', 'proposed'] }, repetitions: 3, seed_policy: '', compute_budget: '' }] })}>{draft.matrix.map((item, index) => <MatrixRow key={index} item={item} onChange={(value) => setDraft({ ...draft, matrix: replace(draft.matrix, index, value) })} onRemove={() => setDraft({ ...draft, matrix: remove(draft.matrix, index) })} />)}</EditorSection>
        <div className="grid gap-5 xl:grid-cols-2"><Lines label={zh ? '决策规则（每行一条）' : 'Decision rules (one per line)'} values={draft.decision_rules} onChange={(decision_rules) => setDraft({ ...draft, decision_rules })} /><Lines label={zh ? '停止条件（每行一条）' : 'Stop conditions (one per line)'} values={draft.stop_conditions} onChange={(stop_conditions) => setDraft({ ...draft, stop_conditions })} /><Lines label={zh ? '可复现清单（每行一条）' : 'Reproducibility checklist'} values={draft.reproducibility} onChange={(reproducibility) => setDraft({ ...draft, reproducibility })} /><EditorSection icon={AlertTriangle} title={zh ? '风险登记' : 'Risk register'} onAdd={() => setDraft({ ...draft, risks: [...draft.risks, { risk: '', mitigation: '', severity: 'medium' }] })}>{draft.risks.map((item, index) => <RiskRow key={index} item={item} onChange={(value) => setDraft({ ...draft, risks: replace(draft.risks, index, value) })} onRemove={() => setDraft({ ...draft, risks: remove(draft.risks, index) })} />)}</EditorSection></div>
        <div className="flex justify-end gap-2 border-t border-border pt-5"><Button variant="secondary" onClick={() => save.mutate('draft')} loading={save.isPending && save.variables === 'draft'}><Save className="h-3.5 w-3.5" />{zh ? '保存草稿' : 'Save draft'}</Button><Button onClick={() => save.mutate('needs_review')} loading={save.isPending && save.variables === 'needs_review'}><Check className="h-3.5 w-3.5" />{zh ? '提交人工复核' : 'Send for review'}</Button></div>
      </main>
      <aside className="border-l border-border bg-surface p-5"><h2 className="text-xs font-semibold text-text">{zh ? '发布门禁' : 'RELEASE GATE'}</h2><div className="mt-4 space-y-2">{issues.length === 0 ? <div className="border-l-2 border-success bg-success-bg p-3 text-xs text-success">{zh ? '所有必需字段与证据检查已通过。' : 'All required fields and evidence checks pass.'}</div> : issues.map((item) => <div key={item} className="flex gap-2 text-xs leading-5 text-muted"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" />{item}</div>)}</div><section className="mt-7 border-t border-border pt-5"><h2 className="flex items-center gap-2 text-xs font-semibold text-text"><History className="h-3.5 w-3.5" />{zh ? '版本历史' : 'Version history'}</h2><div className="mt-3 space-y-2">{(versions.data ?? []).slice(0, 15).map((item) => <div key={item.id} className="flex items-center justify-between bg-surface-2 px-3 py-2"><span className="font-mono text-[10px]">v{item.version}</span><span className="text-[9px] text-faint">{item.source_type}</span></div>)}</div></section>{plan.data?.published_experiment_id && <Link href={`/projects/${projectId}/experiments`} className="mt-6 flex items-center gap-2 border-t border-border pt-4 text-xs font-medium text-accent hover:underline"><Rocket className="h-3.5 w-3.5" />{zh ? '打开已发布实验' : 'Open published experiment'}</Link>}</aside>
    </div>
  </div>;
}

function EditorSection({ icon: Icon, title, subtitle, onAdd, children }: { icon: typeof Variable; title: string; subtitle?: string; onAdd?: () => void; children: React.ReactNode }) { return <section><div className="mb-3 flex items-end justify-between gap-3"><div><h2 className="flex items-center gap-2 text-sm font-semibold text-text"><Icon className="h-4 w-4 text-accent" />{title}</h2>{subtitle && <p className="mt-1 text-[10px] text-faint">{subtitle}</p>}</div>{onAdd && <Button variant="ghost" size="sm" onClick={onAdd}><Plus className="h-3.5 w-3.5" />Add</Button>}</div>{children}</section>; }
function Metric({ label, value }: { label: string; value: string | number }) { return <div><p className="font-mono text-lg font-semibold text-text">{value}</p><p className="text-[10px] text-muted">{label}</p></div>; }
function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) { return <div><Label>{label}</Label><input value={value} onChange={(event) => onChange(event.target.value)} className="mt-1.5 h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-text outline-none focus:ring-2 focus:ring-focus/60" /></div>; }
function Area({ label, value, onChange, rows, wide }: { label: string; value: string; onChange: (value: string) => void; rows: number; wide?: boolean }) { return <div className={wide ? 'xl:col-span-2' : ''}><Label>{label}</Label><textarea value={value} rows={rows} onChange={(event) => onChange(event.target.value)} className="mt-1.5 w-full resize-y rounded-md border border-border-strong bg-surface p-3 text-sm leading-6 text-text outline-none focus:ring-2 focus:ring-focus/60" /></div>; }
function Delete({ onClick }: { onClick: () => void }) { return <button type="button" onClick={onClick} className="text-faint hover:text-danger" aria-label="Remove"><Trash2 className="h-3.5 w-3.5" /></button>; }
const inputClass = 'h-9 rounded-md border border-border-strong bg-bg px-2.5 text-xs text-text outline-none focus:ring-2 focus:ring-focus/60';

function VariableRow({ item, onChange, onRemove }: { item: PlanVariable; onChange: (value: PlanVariable) => void; onRemove: () => void }) { return <div className="grid gap-2 bg-surface p-3 md:grid-cols-[10rem_9rem_1fr_1fr_auto]"><input className={inputClass} value={item.name} placeholder="Variable" onChange={(e) => onChange({ ...item, name: e.target.value })} /><select className={inputClass} value={item.role} onChange={(e) => onChange({ ...item, role: e.target.value as PlanVariable['role'] })}><option value="independent">independent</option><option value="dependent">dependent</option><option value="control">control</option><option value="confounder">confounder</option></select><input className={inputClass} value={item.operational_definition} placeholder="Operational definition" onChange={(e) => onChange({ ...item, operational_definition: e.target.value })} /><input className={inputClass} value={item.levels_or_measurement} placeholder="Levels / measurement" onChange={(e) => onChange({ ...item, levels_or_measurement: e.target.value })} /><Delete onClick={onRemove} /></div>; }
function BaselineRow({ item, papers, zh, onChange, onRemove }: { item: PlanBaseline; papers: Array<{ paper_id: string; title: string }>; zh: boolean; onChange: (value: PlanBaseline) => void; onRemove: () => void }) { return <div className="bg-surface p-3"><div className="flex items-center justify-between gap-3"><Badge size="sm" variant={item.evidence_status === 'grounded' ? 'success' : 'warn'}>{item.evidence_status === 'grounded' ? (zh ? '原文已校验' : 'Grounded') : (zh ? '待补证据' : 'Needs evidence')}</Badge><Delete onClick={onRemove} /></div><div className="mt-3 grid gap-2 md:grid-cols-2"><input className={inputClass} value={item.name} placeholder="Baseline" onChange={(e) => onChange({ ...item, name: e.target.value })} /><select className={inputClass} value={item.source_paper_id ?? ''} onChange={(e) => onChange({ ...item, source_paper_id: e.target.value || null, evidence_status: 'needs_evidence', evidence_section_id: null, evidence_quote: '' })}><option value="">{zh ? '选择任务内论文' : 'Select mission paper'}</option>{papers.map((paper) => <option key={paper.paper_id} value={paper.paper_id}>{paper.title}</option>)}</select><input className={`${inputClass} md:col-span-2`} value={item.rationale} placeholder="Why this baseline?" onChange={(e) => onChange({ ...item, rationale: e.target.value })} /></div>{item.evidence_quote && <blockquote className="mt-3 border-l border-success pl-3 text-[10px] leading-4 text-muted">“{item.evidence_quote}”</blockquote>}</div>; }
function DatasetRow({ item, onChange, onRemove }: { item: PlanDataset; onChange: (value: PlanDataset) => void; onRemove: () => void }) { return <div className="mb-2 grid gap-2 bg-surface p-3"><div className="flex gap-2"><input className={`${inputClass} flex-1`} value={item.name} placeholder="Dataset" onChange={(e) => onChange({ ...item, name: e.target.value })} /><Delete onClick={onRemove} /></div><input className={inputClass} value={item.split} placeholder="Train / validation / test split" onChange={(e) => onChange({ ...item, split: e.target.value })} /><input className={inputClass} value={item.preprocessing} placeholder="Preprocessing" onChange={(e) => onChange({ ...item, preprocessing: e.target.value })} /><input className={inputClass} value={item.license_or_access} placeholder="License / access" onChange={(e) => onChange({ ...item, license_or_access: e.target.value })} /></div>; }
function MetricRow({ item, onChange, onRemove }: { item: PlanMetric; onChange: (value: PlanMetric) => void; onRemove: () => void }) { return <div className="mb-2 grid grid-cols-[1fr_5rem_5rem_auto] gap-2 bg-surface p-3"><input className={inputClass} value={item.name} placeholder="Metric" onChange={(e) => onChange({ ...item, name: e.target.value })} /><select className={inputClass} value={item.direction} onChange={(e) => onChange({ ...item, direction: e.target.value as 'min' | 'max' })}><option value="max">max</option><option value="min">min</option></select><label className="flex items-center gap-1 text-[10px] text-muted"><input type="checkbox" checked={item.primary} onChange={(e) => onChange({ ...item, primary: e.target.checked })} />primary</label><Delete onClick={onRemove} /></div>; }
function MatrixRow({ item, onChange, onRemove }: { item: PlanMatrixRow; onChange: (value: PlanMatrixRow) => void; onRemove: () => void }) { return <div className="mb-2 grid gap-2 bg-surface p-3 md:grid-cols-[1fr_7rem_1fr_1fr_auto]"><input className={inputClass} value={item.name} placeholder="Comparison name" onChange={(e) => onChange({ ...item, name: e.target.value })} /><input className={inputClass} type="number" min={1} value={item.repetitions} onChange={(e) => onChange({ ...item, repetitions: Number(e.target.value) })} /><input className={inputClass} value={item.seed_policy} placeholder="Seed policy" onChange={(e) => onChange({ ...item, seed_policy: e.target.value })} /><input className={inputClass} value={item.compute_budget} placeholder="Compute budget" onChange={(e) => onChange({ ...item, compute_budget: e.target.value })} /><Delete onClick={onRemove} /><code className="text-[10px] text-faint md:col-span-5">factors: {JSON.stringify(item.factors)}</code></div>; }
function RiskRow({ item, onChange, onRemove }: { item: PlanRisk; onChange: (value: PlanRisk) => void; onRemove: () => void }) { return <div className="mb-2 grid gap-2 bg-surface p-3"><div className="flex gap-2"><select className={inputClass} value={item.severity} onChange={(e) => onChange({ ...item, severity: e.target.value as PlanRisk['severity'] })}><option value="high">high</option><option value="medium">medium</option><option value="low">low</option></select><input className={`${inputClass} flex-1`} value={item.risk} placeholder="Risk" onChange={(e) => onChange({ ...item, risk: e.target.value })} /><Delete onClick={onRemove} /></div><input className={inputClass} value={item.mitigation} placeholder="Mitigation" onChange={(e) => onChange({ ...item, mitigation: e.target.value })} /></div>; }
function Lines({ label, values, onChange }: { label: string; values: string[]; onChange: (values: string[]) => void }) { return <div><Label>{label}</Label><textarea rows={8} value={values.join('\n')} onChange={(e) => onChange(e.target.value.split('\n').map((line) => line.trim()).filter(Boolean))} className="mt-1.5 w-full resize-y rounded-md border border-border-strong bg-surface p-3 text-xs leading-6 text-text outline-none focus:ring-2 focus:ring-focus/60" /></div>; }
function replace<T>(items: T[], index: number, value: T) { return items.map((item, cursor) => cursor === index ? value : item); }
function remove<T>(items: T[], index: number) { return items.filter((_, cursor) => cursor !== index); }
function readinessIssues(draft: ExperimentPlanInput, zh: boolean) { const issues: string[] = []; const add = (cn: string, en: string) => issues.push(zh ? cn : en); if (!draft.title.trim()) add('缺少方案标题', 'Plan title is missing'); if (!draft.hypothesis.trim()) add('缺少可证伪假设', 'Falsifiable hypothesis is missing'); const roles = new Set(draft.variables.map((item) => item.role)); if (!roles.has('independent')) add('缺少自变量', 'Independent variable is missing'); if (!roles.has('dependent')) add('缺少因变量', 'Dependent variable is missing'); if (!roles.has('control')) add('缺少控制变量', 'Control variable is missing'); if (!draft.baselines.length) add('缺少对照基线', 'Baseline is missing'); else if (draft.baselines.some((item) => item.evidence_status !== 'grounded')) add('仍有基线未绑定原文证据', 'Baseline evidence is unresolved'); if (!draft.datasets.length) add('缺少数据与切分', 'Dataset and split are missing'); if (!draft.metrics.some((item) => item.primary)) add('缺少主指标', 'Primary metric is missing'); if (!draft.matrix.length) add('实验矩阵为空', 'Experiment matrix is empty'); if (!draft.decision_rules.length) add('缺少决策规则', 'Decision rule is missing'); if (!draft.stop_conditions.length) add('缺少停止条件', 'Stop condition is missing'); if (!draft.risks.length) add('缺少风险登记', 'Risk register is empty'); return issues; }
